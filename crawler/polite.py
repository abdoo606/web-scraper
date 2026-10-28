"""Crawling rules a reviewer would actually accept."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Callable, Protocol
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser


class Http(Protocol):
    def get(self, url: str) -> tuple[int, str]: ...


class LinkExtractor(HTMLParser):
    """Collects <a href> and <title>. html.parser keeps us dependency-free."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())


def extract(html: str) -> tuple[list[str], str]:
    parser = LinkExtractor()
    parser.feed(html)
    return parser.links, parser.title


@dataclass(slots=True)
class Page:
    url: str
    status: int
    title: str
    links: list[str]
    depth: int


@dataclass(slots=True)
class CrawlRules:
    max_pages: int = 20
    max_depth: int = 2
    delay: float = 0.0
    respect_robots: bool = True
    same_host_only: bool = True


@dataclass(slots=True)
class Crawler:
    http: Http
    rules: CrawlRules = field(default_factory=CrawlRules)
    sleeper: Callable[[float], None] = time.sleep
    robots: RobotFileParser | None = None
    pages: list[Page] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def _allowed(self, url: str) -> bool:
        if not self.rules.respect_robots or self.robots is None:
            return True
        return self.robots.can_fetch("*", url)

    def _load_robots(self, base: str) -> None:
        try:
            status, body = self.http.get(urljoin(base, "/robots.txt"))
        except Exception:
            status, body = 404, ""
        parser = RobotFileParser()
        if status == 200:
            parser.parse(body.splitlines())
        else:
            parser.allow_all = True
        self.robots = parser

    def crawl(self, start_url: str) -> list[Page]:
        parsed = urlparse(start_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        self._load_robots(origin)

        queue: list[tuple[str, int]] = [(start_url, 0)]
        seen: set[str] = {start_url}

        while queue and len(self.pages) < self.rules.max_pages:
            url, depth = queue.pop(0)
            if not self._allowed(url):
                self.errors.append(f"blocked by robots.txt: {url}")
                continue
            try:
                status, body = self.http.get(url)
            except Exception as exc:  # network failures never abort a whole crawl
                self.errors.append(f"{url}: {exc}")
                continue
            if status != 200:
                self.errors.append(f"{url}: HTTP {status}")
                continue

            links, title = extract(body)
            self.pages.append(Page(url, status, title, links, depth))
            if self.rules.delay:
                self.sleeper(self.rules.delay)

            if depth >= self.rules.max_depth:
                continue
            for href in links:
                absolute = urljoin(url, href).split("#")[0]
                scheme, netloc = urlparse(absolute).scheme, urlparse(absolute).netloc
                if scheme not in ("http", "https"):
                    continue
                if self.rules.same_host_only and netloc != parsed.netloc:
                    continue
                if absolute not in seen:
                    seen.add(absolute)
                    queue.append((absolute, depth + 1))
        return self.pages
