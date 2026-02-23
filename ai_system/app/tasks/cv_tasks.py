from typing import List, Dict, Any, Optional
from celery import shared_task
import logging
from app.core.cv_pipeline import FaceCVPipeline
from app.core.video_pipeline import VideoProcessor
from app.core.face_search_service import FaceSearchService
from app.db.vector_db import VectorDB
import os

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_image_task(self, image_path: str, metadata: Optional[Dict[str, Any]] = None):
    """
    Background task to process an image: detection, cropping, and embedding extraction.
    Results are stored in ChromaDB.
    """
    logger.info(f"Starting background processing for image: {image_path}")
    
    try:
        pipeline = FaceCVPipeline()
        results = pipeline.process_image(image_path)
        
        if not results:
            logger.warning(f"No faces found in image: {image_path}")
            return {"status": "success", "faces_found": 0}

        vdb = VectorDB()
        
        ids = []
        embeddings = []
        metadatas = []
        
        for i, res in enumerate(results):
            # Generate a unique ID for each detected face
            face_id = f"{os.path.basename(image_path)}_{i}"
            ids.append(face_id)
            embeddings.append(res.embedding)
            
            # Combine image metadata with detection results
            meta = metadata.copy() if metadata else {}
            meta.update({
                "bbox": str(res.bbox),
                "score": float(res.score),
                "original_image": image_path
            })
            metadatas.append(meta)
            
        success = vdb.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas)
        
        if success:
            logger.info(f"Successfully processed and stored {len(results)} faces from {image_path}")
            return {"status": "success", "faces_found": len(results), "ids": ids}
        else:
            logger.error(f"Failed to store embeddings for {image_path}")
            return {"status": "failure", "error": "Storage failure"}

    except Exception as e:
        logger.error(f"Error processing image task: {e}")
        # Retry logic for transient failures (e.g. DB connection)
        try:
            self.retry(exc=e, countdown=60)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for image processing task.")
            return {"status": "failure", "error": str(e)}

@shared_task(bind=True, max_retries=1)
def process_video_task(self, video_path: str, sampling_rate: int = 15):
    """
    Background task to process a video file.
    Samples frames and searches for faces in each.
    """
    logger.info(f"Starting background video processing: {video_path}")
    
    try:
        processor = VideoProcessor(sampling_rate=sampling_rate)
        results = processor.process_video(video_path)
        
        # Cleanup video file if it's in temp directory
        if "temp_uploads" in video_path and os.path.exists(video_path):
            os.remove(video_path)
            logger.info(f"Deleted temp video file: {video_path}")

        return {
            "status": "success",
            "video_path": video_path,
            "detections_count": len(results),
            "results": results
        }

    except Exception as e:
        logger.error(f"Error in process_video_task: {e}")
        return {"status": "failure", "error": str(e)}

@shared_task(bind=True, max_retries=2)
def search_faces_task(self, image_path: str, n_results: int = 5):
    """
    Background task to search for similar faces using an uploaded image.
    Processes the image to extract face embeddings and searches ChromaDB.
    """
    logger.info(f"Starting background face search for image: {image_path}")
    
    try:
        search_service = FaceSearchService()
        
        # Search for similar faces (cleanup=True will delete the temp image)
        result = search_service.search_face_by_image(
            image_path=image_path,
            n_results=n_results,
            cleanup=True
        )
        
        logger.info(f"Face search completed for {image_path}")
        return result

    except Exception as e:
        logger.error(f"Error in search_faces_task: {e}")
        # Retry logic for transient failures
        try:
            self.retry(exc=e, countdown=30)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for face search task.")
            return {"status": "failure", "error": str(e)}
