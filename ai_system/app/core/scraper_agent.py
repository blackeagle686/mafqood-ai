import logging
from typing import Dict, Any, List
from app.core.face_search_service import FaceSearchService
from app.core.nlp_pipeline import classify_text
from urllib.request import urlretrieve
import uuid
import os

logger = logging.getLogger(__name__)

TEMP_DIR = "./temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

class SocialMediaScraperAgent:
    """
    Simulated agent that ingests posts (images + text) from social media sources
    like Facebook groups, runs CV pipelines & NLP, and cross-references with VectorDB.
    """
    
    def __init__(self):
        self.search_service = FaceSearchService()

    def process_social_post(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a social media post dictionary containing an image_url and text content.
        
        Args:
            post_data: Dictionary like:
            {
                "post_id": "12345",
                "source": "facebook_group_A",
                "image_url": "http://example.com/image.jpg",
                "content_text": "Found this child near XYZ street",
                "location": "cairo"
            }
            
        Returns:
            Dictionary with processing results and matches discovered.
        """
        post_id = post_data.get("post_id", "unknown")
        image_url = post_data.get("image_url")
        content_text = post_data.get("content_text", "")
        
        logger.info(f"Scraper Agent intercepting post ID: {post_id}")
        
        if not image_url:
            return {"status": "error", "message": "No image to process"}
            
        # 1. NLP Text Classification (e.g. filter out bad words, spam, or irrelevant posts)
        text_class = classify_text(content_text)
        if text_class == "bad":
             logger.warning(f"Post {post_id} rejected due to bad text content.")
             return {"status": "rejected", "reason": "Text classification failed"}
             
        # 2. Download Image to Temp
        temp_path = os.path.join(TEMP_DIR, f"scraper_{uuid.uuid4()}.jpg")
        try:
            urlretrieve(image_url, temp_path)
            logger.info(f"Downloaded image for post {post_id} to {temp_path}")
        except Exception as e:
             logger.error(f"Failed to download image from {image_url}: {e}")
             return {"status": "error", "message": "Image download failed"}
             
        # 3. Formulate Metadata for Weighting
        # Usually, a scraper infers if the post is "missing" or "found" from the keywords.
        inferred_status = "found" if "عثر" in content_text or "وجد" in content_text else "missing"
        
        query_metadata = {
            "status": inferred_status,
            "location": post_data.get("location", "unknown"),
            "source": post_data.get("source", "social_media"),
            "post_id": post_id
        }
        
        # 4. Search Vector Database using the new weighted pipeline
        try:
             # search_face_by_image will auto-cleanup the temp_path
             results = self.search_service.search_face_by_image(
                 image_path=temp_path,
                 n_results=1,   # Get top match
                 cleanup=True,
                 query_metadata=query_metadata
             )
             
             if results.get("status") == "success" and results.get("faces_detected", 0) > 0:
                 matches = results.get("search_results", [])
                 return {
                     "status": "success",
                     "post_id": post_id,
                     "faces_detected": results["faces_detected"],
                     "matches": matches
                 }
                 
             return {"status": "success", "message": "No matches or faces found."}
             
        except Exception as e:
             logger.error(f"Scraper Agent error processing post {post_id}: {e}")
             return {"status": "error", "message": str(e)}
