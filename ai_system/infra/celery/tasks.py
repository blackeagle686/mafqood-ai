from typing import List, Dict, Any, Optional
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
import logging
from services.face_search_service import FaceSearchService
from services.video_pipeline import VideoProcessor
import os
import time

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def process_image_task(self, image_path: str, metadata: Optional[Dict[str, Any]] = None):
    """
    Background task to process an image: detection, cropping, and embedding extraction.
    Results are stored in ChromaDB.
    
    Retry logic: Retries up to 5 times with 60 second delays for connection issues.
    """
    logger.info(f"Starting background processing for image: {image_path}")
    
    try:
        search_service = FaceSearchService()
        result = search_service.index_image(image_path, metadata)
        
        if result.get("status") == "success":
            logger.info(f"Successfully processed image {image_path}")
            return result
        else:
            logger.error(f"Failed to process image {image_path}: {result.get('message')}")
            raise Exception(result.get("message", "Failed to process image"))

    except SoftTimeLimitExceeded:
        logger.error(f"Task timed out for image {image_path}")
        return {"status": "timeout", "error": "Processing took too long"}
        
    except Exception as e:
        logger.error(f"Error processing image task: {e}")
        # Exponential backoff retry
        try:
            self.retry(exc=e, countdown=min(2 ** self.request.retries * 10, 600))
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for image processing task: {image_path}")
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

@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def search_faces_task(self, image_path: str, n_results: int = 5, use_age_progression: bool = False):
    """
    Background task to search for similar faces using an uploaded image.
    Processes the image to extract face embeddings and searches ChromaDB.
    
    Retry logic: Retries up to 5 times with 60 second delays for connection issues.
    """
    logger.info(f"Starting background face search for image: {image_path}")
    
    try:
        search_service = FaceSearchService()
        
        # Search for similar faces (cleanup=True will delete the temp image)
        result = search_service.search_face_by_image(
            image_path=image_path,
            n_results=n_results,
            cleanup=True,
            use_age_progression=use_age_progression
        )
        
        logger.info(f"Face search completed for {image_path}")
        return result

    except SoftTimeLimitExceeded:
        logger.error(f"Search task timed out for image {image_path}")
        return {"status": "timeout", "error": "Search took too long"}
        
    except Exception as e:
        logger.error(f"Error in search_faces_task: {e}")
        # Exponential backoff retry
        try:
            self.retry(exc=e, countdown=min(2 ** self.request.retries * 10, 600))
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for face search task.")
            return {"status": "failure", "error": str(e)}
