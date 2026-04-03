from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class Face:
    embedding: List[float]
    bbox: List[int]
    score: float
    face_id: Optional[str] = None

@dataclass
class Person:
    name: str
    status: str  # missing, found
    last_seen: Optional[str] = None
    location: Optional[str] = None
    age: Optional[int] = None
    clothing: Optional[str] = None
    details: Optional[str] = None
    images: List[str] = field(default_factory=list)

@dataclass
class FaceMatch:
    face_id: str
    similarity: float
    distance: float
    metadata: Dict[str, Any]
