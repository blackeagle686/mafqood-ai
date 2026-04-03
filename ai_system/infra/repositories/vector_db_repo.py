import chromadb
from chromadb.config import Settings
import logging
from typing import List, Dict, Any, Optional
from app.config import CHROMA_DB_PATH, FACE_COLLECTION_NAME

logger = logging.getLogger(__name__)

class VectorDB:
    """Wrapper for ChromaDB operations to store and search face embeddings."""
    
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(VectorDB, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent re-initialization if already initialized
        if hasattr(self, 'client'):
            return
            
        try:
            self.client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
            self.collection = self.client.get_or_create_collection(
                name=FACE_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"} # Using cosine similarity for embeddings
            )
            logger.info(f"Initialized ChromaDB at {CHROMA_DB_PATH}, collection: {FACE_COLLECTION_NAME}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise

    def upsert(self, ids: List[str], embeddings: List[List[float]], metadatas: Optional[List[Dict[str, Any]]] = None):
        """Insert or update embeddings in the collection."""
        try:
            self.collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas
            )
            logger.info(f"Successfully upserted {len(ids)} embeddings.")
            return True
        except Exception as e:
            logger.error(f"Error during upsert: {e}")
            return False

    def search(self, query_embedding: List[float], n_results: int = 5) -> Dict[str, Any]:
        """Search for the most similar embeddings."""
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            return results
        except Exception as e:
            logger.error(f"Error during search: {e}")
            return {"ids": [], "distances": [], "metadatas": []}

    def delete(self, ids: List[str]):
        """Delete specific embeddings by ID."""
        try:
            self.collection.delete(ids=ids)
            logger.info(f"Successfully deleted embeddings with IDs: {ids}")
            return True
        except Exception as e:
            logger.error(f"Error during delete: {e}")
            return False

    def get_count(self) -> int:
        """Return the number of items in the collection."""
        return self.collection.count()
