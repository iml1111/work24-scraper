import os

from adapters.scraper import parse_listing_ids, parse_total_count

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def read_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


def test_parse_listing_ids():
    html = read_fixture("listing_page.html")
    ids = parse_listing_ids(html)
    assert len(ids) == 10
    assert all(isinstance(id, str) for id in ids)
    assert all(len(id) > 5 for id in ids)
    # All IDs should be unique
    assert len(ids) == len(set(ids))


def test_parse_total_count():
    html = read_fixture("listing_page.html")
    count = parse_total_count(html)
    assert isinstance(count, int)
    assert count > 100000
