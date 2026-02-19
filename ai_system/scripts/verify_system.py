import sys
import os
import numpy as np
import logging

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.cv_pipeline import FaceCVPipeline
from app.db.vector_db import VectorDB

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_pipeline():
    logger.info("--- Verifying CV Pipeline ---")
    pipeline = FaceCVPipeline()
    
    # Create a dummy image (black square)
    dummy_image = np.zeros((500, 500, 3), dtype=np.uint8)
    import cv2
    temp_path = "dummy_face.jpg"
    cv2.imwrite(temp_path, dummy_image)
    
    try:
        # This will likely return 0 faces for a black square, but it tests the initialization
        results = pipeline.process_image(temp_path)
        logger.info(f"Pipeline executed successfully. Detected faces: {len(results)}")
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def verify_vector_db():
    logger.info("--- Verifying Vector DB ---")
    try:
        vdb = VectorDB()
        
        # Test upsert
        test_id = "test_user_1"
        test_embedding = [0.1] * 512 # Dummy embedding
        vdb.upsert(ids=[test_id], embeddings=[test_embedding], metadatas=[{"name": "Test User"}])
        
        # Test search
        results = vdb.search(query_embedding=test_embedding, n_results=1)
        logger.info(f"Search results: {results}")
        
        # Test count
        count = vdb.get_count()
        logger.info(f"Total items in DB: {count}")
        
        # Test delete
        vdb.delete(ids=[test_id])
        logger.info("Deletion successful.")
        
    except Exception as e:
        logger.error(f"Vector DB verification failed: {e}")

if __name__ == "__main__":
    verify_pipeline()
    verify_vector_db()
    logger.info("Verification script finished.")
