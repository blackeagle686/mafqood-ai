from typing import List, Dict, Any, Optional
from celery import shared_task
import logging
from app.core.cv_pipeline import FaceCVPipeline
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
            embeddings.append(res["embedding"])
            
            # Combine image metadata with detection results
            meta = metadata.copy() if metadata else {}
            meta.update({
                "bbox": str(res["bbox"]),
                "score": float(res["score"]),
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
