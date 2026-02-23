from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class FaceDetectionSchema(BaseModel):
    """Schema for a single detected face."""
    bbox: List[float] = Field(..., description="Bounding box of the face [x1, y1, x2, y2]")
    score: float = Field(..., description="Confidence score of the detection")

class FaceEmbeddingSchema(BaseModel):
    """Schema for a face embedding."""
    embedding: List[float] = Field(..., description="512-dimensional face embedding vector")

class PipelineResultSchema(BaseModel):
    """Combined result from the CV pipeline for a single face."""
    bbox: List[float]
    score: float
    embedding: List[float]
    metadata: Optional[Dict[str, Any]] = None

class MissingPersonReportSchema(BaseModel):
    """Schema for reporting a missing person."""
    name: str = Field(..., example="أحمد محمد")
    last_seen: str = Field(..., example="القاهرة، 2024-01-01")
    details: Optional[str] = Field(None, example="كان يرتدي قميصاً أزرق")
    image_path: str

class SearchResultSchema(BaseModel):
    """Schema for a single search result from the vector database."""
    id: str
    distance: float
    metadata: Dict[str, Any]
    similarity: float = Field(..., description="Similarity percentage (0-100)")

class SearchResponseSchema(BaseModel):
    """Comprehensive search response schema."""
    query_image: str
    faces_found: int
    results: List[SearchResultSchema]
