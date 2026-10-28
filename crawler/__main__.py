"""CLI: python -m crawler https://example.com --max-pages 10"""
from __future__ import annotations

import argparse
import urllib.request

from .polite import Crawler, CrawlRules


class UrllibHttp:
    def get(self, url: str) -> tuple[int, str]:
        request = urllib.request.Request(url, headers={"User-Agent": "portfolio-crawler/1.0 (+polite)"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - only http(s)
                return response.status, response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return exc.code, ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="crawler")
    parser.add_argument("url")
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args(argv)

    crawler = Crawler(UrllibHttp(), CrawlRules(max_pages=args.max_pages, max_depth=args.max_depth, delay=args.delay))
    for page in crawler.crawl(args.url):
        print(f"{page.status}  depth={page.depth}  {page.title[:60]:<60} {page.url}")
    for error in crawler.errors:
        print(f"skip: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
