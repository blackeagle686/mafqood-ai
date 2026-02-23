"""Service for face search and vector DB operations."""
import logging
from typing import Dict, Any, List, Optional
from app.core.cv_pipeline import FaceCVPipeline
from app.db.vector_db import VectorDB
from app.core.utils import cleanup_temp_file

logger = logging.getLogger(__name__)


class FaceSearchService:
    """
    Service class for handling face search and vector database operations.
    Encapsulates all face recognition and vector DB logic.
    """
    
    def __init__(self):
        """Initialize the face search service with CV pipeline and vector DB."""
        self.pipeline = FaceCVPipeline()
        self.vdb = VectorDB()
    
    def search_face_by_image(
        self,
        image_path: str,
        n_results: int = 5,
        cleanup: bool = True
    ) -> Dict[str, Any]:
        """
        Search for similar faces in the vector database using an image.
        
        Args:
            image_path: Path to the image file
            n_results: Number of results to return (default: 5)
            cleanup: Whether to cleanup the temp image file after processing (default: True)
            
        Returns:
            Dictionary with search status and results
        """
        try:
            # Process image synchronously to extract face embeddings
            results = self.pipeline.process_image(image_path)
            
            # Cleanup temp file if requested
            if cleanup:
                cleanup_temp_file(image_path)
            
            # If no faces detected
            if not results:
                return {
                    "status": "success",
                    "results": [],
                    "message": "No faces detected in image."
                }
            
            # Take the first detected face for search
            query_embedding = results[0].embedding
            
            # Search in vector database
            search_results = self.vdb.search(query_embedding=query_embedding, n_results=n_results)
            
            return {
                "status": "success",
                "search_results": search_results,
                "faces_detected": len(results)
            }
        except Exception as e:
            logger.error(f"Error in search_face_by_image: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def search_faces_batch(
        self,
        image_paths: List[str],
        n_results: int = 5
    ) -> Dict[str, Any]:
        """
        Search for similar faces using multiple images.
        
        Args:
            image_paths: List of paths to image files
            n_results: Number of results to return per image (default: 5)
            
        Returns:
            Dictionary with batch search results
        """
        try:
            batch_results = []
            
            for image_path in image_paths:
                result = self.search_face_by_image(image_path, n_results=n_results, cleanup=True)
                batch_results.append(result)
            
            return {
                "status": "success",
                "batch_results": batch_results,
                "total_images": len(image_paths)
            }
        except Exception as e:
            logger.error(f"Error in search_faces_batch: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def get_face_count(self) -> int:
        """
        Get the total count of faces in the vector database.
        
        Returns:
            Total count of face embeddings in the database
        """
        try:
            return self.vdb.get_count()
        except Exception as e:
            logger.error(f"Error getting face count: {e}")
            return 0
    
    def delete_faces(self, face_ids: List[str]) -> Dict[str, Any]:
        """
        Delete specific faces from the vector database.
        
        Args:
            face_ids: List of face IDs to delete
            
        Returns:
            Dictionary with deletion status
        """
        try:
            success = self.vdb.delete(ids=face_ids)
            
            if success:
                return {
                    "status": "success",
                    "deleted_count": len(face_ids),
                    "message": f"Successfully deleted {len(face_ids)} faces"
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to delete faces"
                }
        except Exception as e:
            logger.error(f"Error deleting faces: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def get_database_info(self) -> Dict[str, Any]:
        """
        Get information about the vector database.
        
        Returns:
            Dictionary with database statistics
        """
        try:
            face_count = self.get_face_count()
            
            return {
                "status": "success",
                "database_info": {
                    "total_faces": face_count,
                    "database_status": "healthy"
                }
            }
        except Exception as e:
            logger.error(f"Error getting database info: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
