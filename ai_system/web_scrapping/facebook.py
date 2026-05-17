from pathlib import Path
from typing import List, Optional

from .downloader import download_image
from .parser import parse_missing_persons
from .session import FacebookSession
from .models import MissingPerson


class FacebookScraper:
    """High-level helper that ties components together.

    ``scrape_missing`` can be invoked with a Facebook page URL containing
    posts about missing people; the returned list of :class:`MissingPerson`
    objects will be parsed from the HTML.  If ``save_dir`` is supplied the
    scraper will attempt to download any associated images using the
    downloader helper.
    """

    def __init__(self, session: Optional[FacebookSession] = None):
        self.session = session or FacebookSession()

    def fetch_page(self, url: str) -> str:
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.text

    def scrape_missing(
        self, page_url: str, save_dir: Optional[Path] = None
    ) -> List[MissingPerson]:
        html = self.fetch_page(page_url)
        people = parse_missing_persons(html)
        if save_dir:
            save_dir = Path(save_dir)
            save_dir.mkdir(parents=True, exist_ok=True)
            for person in people:
                if person.image_url:
                    try:
                        download_image(person.image_url, str(save_dir))
                    except Exception:
                        # downloading is best-effort; don't fail the whole
                        # scrape if one image is bad.
                        pass
        return people
