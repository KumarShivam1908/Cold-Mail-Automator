from __future__ import annotations

import re
import time
from collections.abc import Callable
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from .config import ScrapeConfig
from .models import Company
from .parser import parse_company_page, parse_company_links


class YCClient:
    def __init__(self, config: ScrapeConfig):
        self.config = config

    def directory_url(self) -> str:
        query: list[tuple[str, str]] = []
        if self.config.hiring_only:
            query.append(("isHiring", "true"))
        query.extend(("batch", batch) for batch in self.config.batches)
        parsed = urlparse(self.config.directory_url)
        return urlunparse(parsed._replace(query=urlencode(query)))

    def fetch(self, url: str) -> str:
        request = Request(
            url,
            headers={"User-Agent": "yc-founder-scraper/0.1 (public directory research)"},
        )
        with urlopen(request, timeout=self.config.request_timeout) as response:
            return response.read().decode("utf-8", errors="replace")

    def scrape(
        self,
        limit: int | None = None,
        on_company: Callable[[Company, int], None] | None = None,
    ) -> list[Company]:
        directory_html = self.fetch(self.directory_url())
        links = parse_company_links(directory_html)
        if not links:
            raise RuntimeError(
                "YC returned no company links in the HTTP response. "
                "The directory is client-rendered; install the browser extra and rerun with --browser."
            )
        if limit is not None:
            links = links[:limit]

        companies: list[Company] = []
        for index, url in enumerate(links):
            if index:
                time.sleep(self.config.delay_seconds)
            company = parse_company_page(self.fetch(url), url)
            companies.append(company)
            if on_company:
                on_company(company, len(companies))
        return companies


class BrowserYCClient(YCClient):
    """Optional Playwright fallback for pages that need JavaScript rendering."""

    def __init__(self, config: ScrapeConfig):
        super().__init__(config)
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Browser mode requires the optional dependency: pip install -e \".[browser]\""
            ) from exc
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._page = self._browser.new_page()

    def fetch(self, url: str) -> str:
        self._page.goto(url, wait_until="domcontentloaded", timeout=self.config.request_timeout * 1000)
        if urlparse(url).path == "/companies":
            # The directory renders company cards after the initial document load.
            self._page.wait_for_selector('a[href^="/companies/"]', timeout=self.config.request_timeout * 1000)
        return self._page.content()

    def _directory_links(self) -> list[str]:
        hrefs = self._page.locator('a[href*="/companies/"]').evaluate_all(
            """anchors => anchors.map(anchor => anchor.href || anchor.getAttribute("href") || "")"""
        )
        links: list[str] = []
        seen: set[str] = set()
        for href in hrefs:
            if not href:
                continue
            parsed = urlparse(href)
            if parsed.path == "/companies" or not parsed.path.startswith("/companies/"):
                continue
            url = urlunparse(parsed._replace(query="", fragment=""))
            if url not in seen:
                seen.add(url)
                links.append(url)
        return links

    def _load_all_directory_links(self, limit: int | None = None) -> list[str]:
        stagnant_rounds = 0
        previous_count = 0
        while True:
            links = self._directory_links()
            if limit is not None and len(links) >= limit:
                return links[:limit]
            if len(links) > previous_count:
                previous_count = len(links)
                stagnant_rounds = 0
            else:
                stagnant_rounds += 1
            if stagnant_rounds >= 3:
                return links

            button = self._page.get_by_role("button", name=re.compile(r"(show|load) more", re.IGNORECASE)).first
            if button.count():
                button.click()
            else:
                self._page.mouse.wheel(0, 4000)
            self._page.wait_for_timeout(1500)

    def scrape(
        self,
        limit: int | None = None,
        on_company: Callable[[Company, int], None] | None = None,
    ) -> list[Company]:
        directory_url = self.directory_url()
        self._page.goto(directory_url, wait_until="domcontentloaded", timeout=self.config.request_timeout * 1000)
        self._page.wait_for_selector('a[href*="/companies/"]', timeout=self.config.request_timeout * 1000)
        links = self._load_all_directory_links(limit)

        if not links:
            raise RuntimeError(
                "YC returned no company links in browser mode. "
                "The directory markup likely changed and the link selector needs to be updated."
            )

        companies: list[Company] = []
        for index, url in enumerate(links):
            if index:
                time.sleep(self.config.delay_seconds)
            company = parse_company_page(self.fetch(url), url)
            companies.append(company)
            if on_company:
                on_company(company, len(companies))
        return companies

    def close(self) -> None:
        self._browser.close()
        self._playwright.stop()
