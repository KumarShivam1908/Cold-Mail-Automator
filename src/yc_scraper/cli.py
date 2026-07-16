from __future__ import annotations

import argparse

from .client import BrowserYCClient, YCClient
from .config import DEFAULT_BATCHES, ScrapeConfig
from .exporters import write_csv, write_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape public YC company and founder data.")
    parser.add_argument("--output", default="data/yc-founders.json", help="JSON output path")
    parser.add_argument("--csv", dest="csv_output", default=None, help="Optional CSV output path")
    parser.add_argument("--limit", type=int, default=None, help="Limit companies for a test run")
    parser.add_argument("--browser", action="store_true", help="Use the optional standard Chromium fallback")
    parser.add_argument("--no-hiring-filter", action="store_true", help="Include companies that are not hiring")
    parser.add_argument("--batch", action="append", dest="batches", help="Override default batch list; repeatable")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = ScrapeConfig(
        hiring_only=not args.no_hiring_filter,
        batches=args.batches or list(DEFAULT_BATCHES),
    )
    client = BrowserYCClient(config) if args.browser else YCClient(config)
    companies = []
    write_json(companies, args.output)

    def persist_company(company, _count) -> None:
        companies.append(company)
        write_json(companies, args.output)

    try:
        client.scrape(args.limit, on_company=persist_company)
    finally:
        if isinstance(client, BrowserYCClient):
            client.close()
    if args.csv_output:
        write_csv(companies, args.csv_output)
    print(f"Scraped {len(companies)} companies")
    print(f"JSON: {args.output}")
    if args.csv_output:
        print(f"CSV: {args.csv_output}")


if __name__ == "__main__":
    main()
