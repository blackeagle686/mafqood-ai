import os
from dataclasses import dataclass

@dataclass
class Config:
    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8000
    redis_url: str = "redis://localhost:6379/0"
    chroma_url: str = os.getenv("CHROMA_URL", "http://localhost:8001")
    
    # ChromaDB Persistence
    chroma_db_path: str = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    face_collection_name: str = "face_embeddings"

    # CV Model Config
    # ctx_id: -1 for CPU, 0 for GPU
    cv_ctx_id: int = int(os.getenv("CV_CTX_ID", "-1"))
    face_analysis_model: str = "buffalo_l"

config = Config()

# For direct access (backward compatibility or simpler imports)
CHROMA_DB_PATH = config.chroma_db_path
FACE_COLLECTION_NAME = config.face_collection_name
CV_CTX_ID = config.cv_ctx_id
FACE_ANALYSIS_MODEL = config.face_analysis_model
