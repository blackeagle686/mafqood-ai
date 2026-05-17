import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# make sure project root is on import path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_scrapping.parser import parse_missing_persons
from web_scrapping.downloader import download_image
from web_scrapping.facebook import FacebookScraper


# sample HTML that matches the simplistic parser in this package
SAMPLE_HTML = """
<html>
<body>
<div class="missing-person">
    <span class="name">Alice</span>
    <span class="age">25</span>
    <p class="details">Last seen at park</p>
    <img src="http://example.com/alice.jpg"/>
</div>
<div class="missing-person">
    <span class="name">Bob</span>
    <span class="details">Unknown details</span>
</div>
</body>
</html>
"""


def test_parse_missing_persons():
    people = parse_missing_persons(SAMPLE_HTML)
    assert len(people) == 2
    assert people[0].name == "Alice"
    assert people[0].age == "25"
    assert people[0].details == "Last seen at park"
    assert people[0].image_url == "http://example.com/alice.jpg"

    assert people[1].name == "Bob"
    assert people[1].age is None
    assert people[1].image_url is None


def test_download_image(tmp_path, monkeypatch):
    # stub out requests.get so that no network call is made
    dummy_data = b"12345"

    class DummyResp:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size=1):
            yield dummy_data

    import requests

    monkeypatch.setattr(requests, "get", lambda url, stream=True: DummyResp())

    out = download_image("http://example.com/pic.jpg", tmp_path)
    assert os.path.exists(out)
    assert open(out, "rb").read() == dummy_data


def test_facebook_scraper(monkeypatch, tmp_path):
    fake_resp = MagicMock()
    fake_resp.text = SAMPLE_HTML
    fake_resp.raise_for_status.return_value = None

    class DummySession:
        def get(self, url):
            return fake_resp

    scraper = FacebookScraper(session=DummySession())

    # the scraper imported the helper directly, patch that name instead
    from web_scrapping import facebook

    def fake_download(url, dest):
        path = Path(dest) / "alice.jpg"
        with open(path, "wb") as f:
            f.write(b"x")
        return str(path)

    monkeypatch.setattr(facebook, "download_image", fake_download)

    people = scraper.scrape_missing("http://fake-url", save_dir=tmp_path)
    assert len(people) == 2
    # ensure patched downloader produced a file
    assert (tmp_path / "alice.jpg").exists()
