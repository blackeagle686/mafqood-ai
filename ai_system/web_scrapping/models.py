from dataclasses import dataclass
from typing import Optional


@dataclass
class MissingPerson:
    """Represents a missing person entry scraped from Facebook."""

    name: str
    age: Optional[str] = None
    details: Optional[str] = None
    image_url: Optional[str] = None
