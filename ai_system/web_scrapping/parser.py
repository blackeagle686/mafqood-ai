from typing import List

from bs4 import BeautifulSoup

from .models import MissingPerson


def parse_missing_persons(html: str) -> List[MissingPerson]:
    """Extract a list of :class:`MissingPerson` objects from a block of HTML.

    The small example implementation below looks for a very specific
    hypothetical markup structure containing a ``<div class="missing-person">``
    element for each person.  The format is deliberately loose so that the
    parser can be reused when the real Facebook layout changes; callers can
    always customise it or replace it with a subclass.
    """
    soup = BeautifulSoup(html, "html.parser")
    results: List[MissingPerson] = []

    for div in soup.find_all("div", class_="missing-person"):
        name_tag = div.find(class_="name")
        age_tag = div.find(class_="age")
        details_tag = div.find(class_="details")
        img_tag = div.find("img")

        person = MissingPerson(
            name=name_tag.get_text(strip=True) if name_tag else "",
            age=age_tag.get_text(strip=True) if age_tag else None,
            details=details_tag.get_text(strip=True) if details_tag else None,
            image_url=img_tag["src"] if img_tag and img_tag.has_attr("src") else None,
        )
        results.append(person)

    return results
