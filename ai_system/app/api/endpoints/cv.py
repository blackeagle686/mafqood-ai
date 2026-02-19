from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
import shutil
import os
import uuid
import logging
from typing import List, Dict, Any
from app.core.cv_pipeline import FaceCVPipeline
from app.db.vector_db import VectorDB
from app.tasks.cv_tasks import process_image_task

logger = logging.getLogger(__name__)
router = APIRouter()

TEMP_UPLOAD_DIR = "./temp_uploads"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

@router.post("/process")
async def process_image(file: UploadFile = File(...)):
    """
    Async endpoint to process an image for face embeddings.
    Saves image and dispatches a Celery task.
    """
    try:
        # Save uploaded file to temp directory
        ext = os.path.splitext(file.filename)[1]
        temp_filename = f"{uuid.uuid4()}{ext}"
        temp_path = os.path.join(TEMP_UPLOAD_DIR, temp_filename)
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Dispatch Celery task
        # Note: In a real prod environment, you'd pass the absolute path
        abs_path = os.path.abspath(temp_path)
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
async def search_face(file: UploadFile = File(...)):
    """
    Synchronous search endpoint. 
    Processes the uploaded image to get an embedding and searches ChromaDB.
    """
    try:
        # Save temp file
        ext = os.path.splitext(file.filename)[1]
        temp_path = os.path.join(TEMP_UPLOAD_DIR, f"search_{uuid.uuid4()}{ext}")
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Run pipeline synchronously for immediate search
        pipeline = FaceCVPipeline()
        results = pipeline.process_image(temp_path)
        
        # Cleanup temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        if not results:
            return {"status": "success", "results": [], "message": "No faces detected in image."}
            
        # Take the first detected face for search
        query_embedding = results[0]["embedding"]
        
        vdb = VectorDB()
        search_results = vdb.search(query_embedding=query_embedding, n_results=5)
        
        return {
            "status": "success",
            "search_results": search_results
        }
    except Exception as e:
        logger.error(f"Error in /search endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """Health check for the CV service."""
    return {"status": "healthy", "service": "cv_pipeline"}
