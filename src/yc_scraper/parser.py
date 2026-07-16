from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin

from .models import Company, Founder


NON_PERSON_TERMS = {
    "ai",
    "agent",
    "agents",
    "broker",
    "company",
    "copilot",
    "data",
    "engineering",
    "financial",
    "infrastructure",
    "marketing",
    "mortgage",
    "native",
    "operations",
    "operating",
    "platform",
    "product",
    "sales",
    "science",
    "software",
    "support",
    "team",
    "teams",
    "tools",
}


def clean(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", " ", value).strip() or None


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[dict[str, str]] = []
        self.title = ""
        self.meta: dict[str, str] = {}
        self.text: list[str] = []
        self.headings: list[str] = []
        self._in_title = False
        self._in_heading = False
        self._heading_text = ""
        self._container_stack: list[dict[str, list[str]]] = []
        self._anchor: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            key = values.get("property") or values.get("name")
            content = values.get("content")
            if key and content:
                self.meta[key] = content
        if tag in {"h1", "h2", "h3", "h4"}:
            self._in_heading = True
            self._heading_text = ""
        if tag in {"article", "div", "li", "section"}:
            self._container_stack.append({"tag": tag, "text": []})
        if tag == "a" and values.get("href"):
            self._anchor = {
                "href": values["href"] or "",
                "text": "",
                "heading": self._heading_text,
                "context": " ".join(self._container_stack[-1]["text"][-3:]) if self._container_stack else "",
            }

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in {"h1", "h2", "h3", "h4"}:
            value = clean(self._heading_text)
            if value:
                self.headings.append(value)
            self._in_heading = False
        if tag == "a" and self._anchor:
            self.links.append(self._anchor)
            self._anchor = None
        if tag in {"article", "div", "li", "section"} and self._container_stack:
            container = self._container_stack.pop()
            value = clean(" ".join(container["text"]))
            if value and self._container_stack:
                self._container_stack[-1]["text"].append(value)

    def handle_data(self, data: str) -> None:
        value = clean(data)
        if not value:
            return
        self.text.append(value)
        if self._container_stack:
            self._container_stack[-1]["text"].append(value)
        if self._in_title:
            self.title += f" {value}"
        if self._in_heading:
            self._heading_text += f" {value}"
        if self._anchor:
            self._anchor["text"] += f" {value}"


def parse_company_links(html: str, base_url: str = "https://www.ycombinator.com") -> list[str]:
    parser = _LinkParser()
    parser.feed(html)
    links: list[str] = []
    seen: set[str] = set()
    for link in parser.links:
        href = link["href"]
        if not href.startswith("/companies/") or href == "/companies/":
            continue
        url = urljoin(base_url, href.split("?")[0].split("#")[0])
        if url not in seen:
            seen.add(url)
            links.append(url)
    return links


def _fallback_founder_name(linkedin_url: str) -> str:
    slug = linkedin_url.rstrip("/").split("/")[-1]
    return re.sub(r"[-_]+", " ", slug).title()


def _context_founder_name(context: str | None) -> str | None:
    if not context:
        return None
    for chunk in re.split(r"\s{2,}|[|•·]", context):
        value = clean(chunk)
        if not value or "/" in value or "@" in value or len(value.split()) > 4:
            continue
        if re.fullmatch(r"[A-Z][A-Za-z'`.-]+(?:\s+[A-Z][A-Za-z'`.-]+){1,3}", value):
            return value
    return None


def _looks_like_person_name(value: str | None) -> str | None:
    cleaned = clean(value)
    if not cleaned:
        return None
    if not re.fullmatch(r"[A-Z][A-Za-z'`.-]+(?:\s+[A-Z][A-Za-z'`.-]+){1,3}", cleaned):
        return None
    tokens = re.findall(r"[A-Za-z]+", cleaned)
    if len(tokens) < 2:
        return None
    if any(token.lower() in NON_PERSON_TERMS for token in tokens):
        return None
    if any(token.isupper() and len(token) > 1 for token in tokens):
        return None
    return cleaned


def _normalize_linkedin(linkedin_url: str) -> str:
    return re.sub(r"[?#].*$", "", linkedin_url).rstrip("/")


def _description_founder_names(description: str | None) -> list[str]:
    cleaned = clean(description)
    if not cleaned:
        return []
    match = re.search(r"Founded in \d{4} by (.+?)(?:, [^.]*|\.)", cleaned)
    if not match:
        return []
    segment = clean(match.group(1))
    if not segment:
        return []
    candidates: list[str] = []
    for chunk in segment.replace(" and ", ", ").split(","):
        candidate = _looks_like_person_name(chunk)
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _match_founder_name_from_candidates(linkedin_url: str, candidates: list[str]) -> str | None:
    slug = re.sub(r"[^a-z]", "", _normalize_linkedin(linkedin_url).split("/")[-1].lower())
    if not slug:
        return None
    best_match: str | None = None
    best_score = 0
    for candidate in candidates:
        normalized = re.sub(r"[^a-z]", "", candidate.lower())
        if len(normalized) < 6:
            continue
        if normalized == slug:
            return candidate
        score = 0
        if slug.startswith(normalized) or normalized.startswith(slug):
            score = len(normalized)
        elif normalized in slug or slug in normalized:
            score = min(len(normalized), len(slug))
        if score > best_score:
            best_score = score
            best_match = candidate
    return best_match


def _page_founder_name(linkedin_url: str, texts: list[str]) -> str | None:
    candidates: list[str] = []
    for text in texts:
        for match in re.findall(r"\b[A-Z][A-Za-z'`.-]+(?:\s+[A-Z][A-Za-z'`.-]+){1,3}\b", text):
            value = _looks_like_person_name(match)
            if value and value not in candidates:
                candidates.append(value)
    return _match_founder_name_from_candidates(linkedin_url, candidates)


def parse_company_page(html: str, url: str) -> Company:
    parser = _LinkParser()
    parser.feed(html)
    title = clean(parser.meta.get("og:title") or parser.title)
    name = clean(title.split(":", 1)[0] if title else None) or url.rstrip("/").split("/")[-1].replace("-", " ").title()
    website = next(
        (link["href"] for link in parser.links
         if link["href"].startswith("http")
         and "ycombinator.com" not in link["href"]
         and "linkedin.com" not in link["href"]),
        None,
    )
    batch_match = re.search(r"\b(?:Winter|Spring|Summer|Fall) \d{4}\b", " ".join(parser.text))
    industries: list[str] = []
    for link in parser.links:
        if "/companies?industry=" in link["href"]:
            value = clean(link["text"])
            if value and value not in industries:
                industries.append(value)
    description = clean(parser.meta.get("description") or parser.meta.get("og:description"))
    description_candidates = _description_founder_names(description)
    founders: list[Founder] = []
    seen_linkedin: set[str] = set()
    for link in parser.links:
        linkedin = link["href"]
        normalized_linkedin = _normalize_linkedin(linkedin)
        if "linkedin.com/in/" in linkedin and normalized_linkedin not in seen_linkedin:
            seen_linkedin.add(normalized_linkedin)
            founder_name = (
                _match_founder_name_from_candidates(normalized_linkedin, description_candidates)
                or
                _looks_like_person_name(link["heading"])
                or _context_founder_name(link.get("context"))
                or _page_founder_name(normalized_linkedin, parser.text)
                or _fallback_founder_name(normalized_linkedin)
            )
            founders.append(Founder(founder_name, normalized_linkedin))
    return Company(
        name=name,
        yc_url=url,
        batch=batch_match.group(0) if batch_match else None,
        website=website,
        industries=industries,
        one_liner=parser.headings[0] if parser.headings else None,
        description=description,
        founders=founders,
    )
