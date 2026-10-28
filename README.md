# 20 · crawler

A polite crawler: robots.txt, rate limits, deduplication, no dependencies.

## Run

```bash
from crawler.polite import Crawler, CrawlRules
```

## Test

```bash
pytest projects/20-web-scraper -q
```

## What it demonstrates

- `urllib.robotparser` is honoured before every request
- Per-host rate limiting and a page/depth budget
- Network failures are recorded as data, never abort the crawl
- HTTP client injected, so the whole crawl is tested with a dictionary of pages
