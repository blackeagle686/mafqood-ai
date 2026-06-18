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

@shared_task(bind=True)
def background_cross_match_task(self, batch_size: int = 50):
    """
    Background Task: Triggers the cross-match reconciliation job.
    Iterates through missing items and cross-checks them against found items.
    """
    logger.info("Starting background cross-match reconciliation task...")
    try:
        search_service = FaceSearchService()
        search_service.cross_match_background(batch_size=batch_size)
        return {"status": "success", "message": "Reconciliation completed"}
    except Exception as e:
        logger.error(f"Error in background reconciliation task: {e}")
        return {"status": "failure", "error": str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_webhook_task(self, payload: Dict[str, Any]):
    """
    Background task to deliver a match results callback payload to the Mafqood system.
    Supports retries on failure.
    """
    from infra.external.webhook_notifier import WebhookNotifier
    logger.info(f"Asynchronously triggering webhook notification payload: {payload}")
    
    success = WebhookNotifier.send_match_results_to_mafqood(payload)
    if not success:
        # Retry with exponential backoff
        countdown = 2 ** self.request.retries * 10
        logger.warning(f"Webhook delivery failed, scheduling retry in {countdown} seconds...")
        self.retry(countdown=countdown)
    
    return {"status": "success"}


@shared_task(bind=True)
def background_dna_match_task(self, post_id: int):
    """
    Background task to compare a post's DNA profile against all active posts of the opposite status.
    Saves high-confidence matches and dispatches webhook notifications.
    """
    from app.ai.models import Post, DNAProfile, DNAMatch
    from services.dna_search_service import DNASearchService
    
    logger.info(f"Starting background DNA match reconciliation for postId: {post_id}")
    
    try:
        # 1. Fetch current DNA profile and related post
        current_profile = DNAProfile.objects.get(post__post_id=post_id)
        current_post = current_profile.post
        
        # Don't match resolved posts
        if current_post.is_resolved:
            logger.info(f"Post {post_id} is already resolved. Skipping DNA matching.")
            return {"status": "skipped", "message": "Post is resolved"}

        # 2. Query opposite-status unresolved posts with DNA profiles
        opposite_type = 1 if current_post.post_type == 0 else 0
        opposite_profiles = DNAProfile.objects.filter(
            post__post_type=opposite_type,
            post__is_resolved=False
        )
        
        if not opposite_profiles.exists():
            logger.info(f"No opposite status DNA profiles found to compare with postId {post_id}.")
            return {"status": "completed", "matches_found": 0}
            
        targets = []
        for profile in opposite_profiles:
            targets.append({
                "id": profile.post.post_id,
                "str_data": profile.str_data,
                "metadata": {
                    "userId": profile.post.user_id,
                    "postType": profile.post.post_type,
                    "gender": profile.gender
                }
            })
            
        # 3. Perform matching using DNASearchService
        dna_service = DNASearchService()
        
        # Run direct matches
        direct_results = dna_service.search_profiles(
            query_profile=current_profile.str_data,
            target_profiles=targets,
            search_type="direct",
            min_overlap=3
        )
        
        # Run parent-child matches
        kinship_results = dna_service.search_profiles(
            query_profile=current_profile.str_data,
            target_profiles=targets,
            search_type="parent_child",
            min_overlap=3
        )
        
        matches_recorded = 0
        
        # Process direct matches
        for res in direct_results:
            if res["score"] == 1.0:
                missing_id = post_id if current_post.post_type == 0 else res["target_id"]
                found_id = res["target_id"] if current_post.post_type == 0 else post_id
                
                dna_match, created = DNAMatch.objects.get_or_create(
                    missing_post_id=missing_id,
                    found_post_id=found_id,
                    defaults={
                        "match_type": "direct",
                        "overlap_loci_count": res["overlap_count"],
                        "matching_loci_count": res["details"]["overlap_count"] - len(res["details"]["mismatches"]),
                        "confidence_score": 1.0
                    }
                )
                if created:
                    matches_recorded += 1
                    # Dispatch webhook
                    payload = {
                        "userId": current_post.user_id if current_post.post_type == 0 else res["metadata"]["userId"],
                        "postId": missing_id,
                        "matchedResults": [
                            {
                                "userId": res["metadata"]["userId"] if current_post.post_type == 0 else current_post.user_id,
                                "postId": found_id,
                                "confidenceScore": 1.0,
                                "relationshipType": "direct"
                            }
                        ]
                    }
                    send_dna_webhook_task.delay(payload)
                    
        # Process kinship parent-child matches
        for res in kinship_results:
            if res["score"] == 1.0:
                missing_id = post_id if current_post.post_type == 0 else res["target_id"]
                found_id = res["target_id"] if current_post.post_type == 0 else post_id
                
                dna_match, created = DNAMatch.objects.get_or_create(
                    missing_post_id=missing_id,
                    found_post_id=found_id,
                    defaults={
                        "match_type": "kinship_parent_child",
                        "overlap_loci_count": res["overlap_count"],
                        "matching_loci_count": len(res["details"]["compatible_loci"]),
                        "confidence_score": 1.0
                    }
                )
                if created:
                    matches_recorded += 1
                    # Dispatch webhook
                    payload = {
                        "userId": current_post.user_id if current_post.post_type == 0 else res["metadata"]["userId"],
                        "postId": missing_id,
                        "matchedResults": [
                            {
                                "userId": res["metadata"]["userId"] if current_post.post_type == 0 else current_post.user_id,
                                "postId": found_id,
                                "confidenceScore": 1.0,
                                "relationshipType": "kinship_parent_child"
                            }
                        ]
                    }
                    send_dna_webhook_task.delay(payload)

        return {"status": "completed", "matches_found": matches_recorded}

    except DNAProfile.DoesNotExist:
        logger.error(f"DNA Profile for postId {post_id} not found.")
        return {"status": "failed", "error": "Profile not found"}
    except Exception as e:
        logger.error(f"Error in background_dna_match_task: {e}")
        return {"status": "failed", "error": str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_dna_webhook_task(self, payload: Dict[str, Any]):
    """
    Background task to deliver a DNA match results callback payload to the Mafqood system.
    Supports retries on failure.
    """
    from infra.external.webhook_notifier import WebhookNotifier
    logger.info(f"Asynchronously triggering DNA webhook notification payload: {payload}")
    
    success = WebhookNotifier.send_dna_match_results_to_mafqood(payload)
    if not success:
        countdown = 2 ** self.request.retries * 10
        logger.warning(f"DNA Webhook delivery failed, scheduling retry in {countdown} seconds...")
        self.retry(countdown=countdown)
    
    return {"status": "success"}

@shared_task(bind=True)
def evaluate_and_trigger_clustering(self):
    """
    Background Task: Triggers the clustering operation periodically.
    """
    from services.clustering_service import ClusteringAgent
    logger.info("Starting background clustering task...")
    try:
        agent = ClusteringAgent()
        result = agent.perform_clustering()
        logger.info(f"Clustering completed with result: {result}")
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"Error in background clustering task: {e}")
        return {"status": "failure", "error": str(e)}

@shared_task(bind=True)
def poll_facebook_groups_task(self):
    """
    Background Task: Periodically polls Facebook groups for missing person posts.
    """
    logger.info("Starting background Facebook group polling task...")
    try:
        from web_scrapping.facebook import FacebookScraper
        scraper = FacebookScraper()
        # TODO: Implement reading from a list of group URLs and processing results
        logger.info("Facebook group polling completed.")
        return {"status": "success", "message": "Polling stub completed"}
    except Exception as e:
        logger.error(f"Error in background Facebook group polling task: {e}")
        return {"status": "failure", "error": str(e)}
