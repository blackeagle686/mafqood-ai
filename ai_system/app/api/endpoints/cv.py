from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
import logging
from typing import List, Dict, Any
from app.core.face_search_service import FaceSearchService
from app.tasks.cv_tasks import process_image_task, process_video_task, search_faces_task
from app.core.utils import save_uploaded_file

logger = logging.getLogger(__name__)
router = APIRouter()

TEMP_UPLOAD_DIR = "./temp_uploads"

# Initialize the face search service
face_search_service = FaceSearchService()

@router.post("/process")
async def process_image(file: UploadFile = File(...)):
    """
    Async endpoint to process an image for face embeddings.
    Saves image and dispatches a Celery task.
    """
    try:
        # Save uploaded file to temp directory
        abs_path = save_uploaded_file(file, temp_upload_dir=TEMP_UPLOAD_DIR)
            
        # Dispatch Celery task
        task = process_image_task.delay(abs_path)
        
        return {
            "status": "queued",
            "task_id": task.id,
            "filename": file.filename,
            "temp_path": abs_path
        }
    except Exception as e:
        logger.error(f"Error in /process endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search")
async def search_face(file: UploadFile = File(...), n_results: int = 5):
    """
    Async endpoint to search for similar faces using an uploaded image.
    Dispatches a background Celery task for face search and vector DB queries.
    
    Args:
        file: Image file to search with
        n_results: Number of similar faces to return (default: 5)
    """
    try:
        # Save temp file
        temp_path = save_uploaded_file(file, temp_upload_dir=TEMP_UPLOAD_DIR, prefix="search")
            
        # Dispatch Celery task for background face search
        task = search_faces_task.delay(temp_path, n_results=n_results)
        
        return {
            "status": "queued",
            "task_id": task.id,
            "filename": file.filename,
            "n_results": n_results,
            "message": "Face search queued for processing"
        }
    except Exception as e:
        logger.error(f"Error in /search endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process_video")
async def process_video(file: UploadFile = File(...), sampling_rate: int = 15):
    """
    Async endpoint to process a video file.
    Saves video and dispatches a Celery task.
    """
    try:
        # Save uploaded file to temp directory
        abs_path = save_uploaded_file(file, temp_upload_dir=TEMP_UPLOAD_DIR, prefix="video")
            
        # Dispatch Celery task
        task = process_video_task.delay(abs_path, sampling_rate=sampling_rate)
        
        return {
            "status": "queued",
            "task_id": task.id,
            "filename": file.filename,
            "sampling_rate": sampling_rate
        }
    except Exception as e:
        logger.error(f"Error in /process_video endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """Health check for the CV service."""
    return {"status": "healthy", "service": "cv_pipeline"}

@router.get("/database/info")
async def get_database_info():
    """
    Get information about the face vector database.
    Returns the total count of faces stored.
    """
    try:
        info = face_search_service.get_database_info()
        return info
    except Exception as e:
        logger.error(f"Error in /database/info endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/faces")
async def delete_faces(face_ids: List[str]):
    """
    Delete specific faces from the vector database.
    
    Args:
        face_ids: List of face IDs to delete
    """
    try:
        result = face_search_service.delete_faces(face_ids)
        return result
    except Exception as e:
        logger.error(f"Error in /faces delete endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
