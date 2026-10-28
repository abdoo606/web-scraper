from __future__ import annotations

import pytest

from crawler.polite import Crawler, CrawlRules, Page, extract

SITE = {
    "https://site.test/robots.txt": "User-agent: *\nDisallow: /private\n",
    "https://site.test/": '<title>Home</title><a href="/a">A</a><a href="/private/x">P</a>',
    "https://site.test/a": '<title>Page A</title><a href="/b">B</a><a href="https://other.test/x">X</a>',
    "https://site.test/b": '<title>Page B</title><a href="/">home</a>',
    "https://site.test/private/x": "<title>Secret</title>",
}


class FakeHttp:
    def __init__(self, site: dict[str, str], fail: set[str] | None = None) -> None:
        self.site = site
        self.fail = fail or set()
        self.requested: list[str] = []

    def get(self, url: str) -> tuple[int, str]:
        self.requested.append(url)
        if url in self.fail:
            raise ConnectionError("boom")
        if url in self.site:
            return 200, self.site[url]
        return 404, ""


def test_extract_links_and_title():
    links, title = extract('<title>Hello  World</title><a href="/x">x</a>')
    assert links == ["/x"] and title == ("Hello World")


def test_extract_ignores_anchorless_tags():
    assert extract("<a>no href</a><a href=''>empty</a>")[0] == []


def test_crawl_follows_internal_links():
    pages = Crawler(FakeHttp(SITE)).crawl("https://site.test/")
    assert [p.url for p in pages] == ["https://site.test/", "https://site.test/a", "https://site.test/b"]


def test_robots_txt_is_respected():
    crawler = Crawler(FakeHttp(SITE))
    crawler.crawl("https://site.test/")
    assert all("/private" not in p.url for p in crawler.pages)
    assert any("robots" in e for e in crawler.errors)


def test_robots_can_be_disabled():
    crawler = Crawler(FakeHttp(SITE), CrawlRules(respect_robots=False, max_depth=1))
    urls = [p.url for p in crawler.crawl("https://site.test/")]
    assert "https://site.test/private/x" in urls


def test_external_links_are_not_followed_by_default():
    crawler = Crawler(FakeHttp(SITE))
    crawler.crawl("https://site.test/")
    assert not any("other.test" in u for u in crawler.http.requested)


def test_max_depth_limits_the_crawl():
    pages = Crawler(FakeHttp(SITE), CrawlRules(max_depth=0)).crawl("https://site.test/")
    assert len(pages) == 1


def test_max_pages_limits_the_crawl():
    pages = Crawler(FakeHttp(SITE), CrawlRules(max_pages=2)).crawl("https://site.test/")
    assert len(pages) == 2


def test_each_url_is_fetched_once():
    crawler = Crawler(FakeHttp(SITE))
    crawler.crawl("https://site.test/")
    assert len(crawler.http.requested) == len(set(crawler.http.requested))


def test_network_errors_are_recorded_not_raised():
    http = FakeHttp(SITE, fail={"https://site.test/a"})
    crawler = Crawler(http)
    pages = crawler.crawl("https://site.test/")
    assert any("boom" in e for e in crawler.errors)
    assert len(pages) >= 1


def test_missing_robots_allows_everything():
    http = FakeHttp({"https://site.test/": "<title>x</title>"})
    assert len(Crawler(http).crawl("https://site.test/")) == 1


def test_delay_sleeps_between_pages():
    slept: list[float] = []
    crawler = Crawler(FakeHttp(SITE), CrawlRules(delay=0.5), sleeper=slept.append)
    crawler.crawl("https://site.test/")
    assert slept and all(s == 0.5 for s in slept)


def test_page_is_a_value_object():
    page = Page("u", 200, "t", [], 0)
    assert page.url == "u" and page.depth == 0
