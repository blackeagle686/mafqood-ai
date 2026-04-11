"""Service for face search and vector DB operations."""
import logging
from typing import Dict, Any, List, Optional
from services.cv_service import FaceCVPipeline
from infra.repositories.vector_db_repo import VectorDB
from utils.file_utils import cleanup_temp_file
from infra.external.webhook_notifier import WebhookNotifier
from services.age_progression_service import AgeProgressionGAN

from datetime import datetime
from app.ai.models import FaceMatch

logger = logging.getLogger(__name__)


class FaceSearchService:
    """
    Service class for handling face search and vector database operations.
    Encapsulates all face recognition and vector DB logic.
    """
    
    @staticmethod
    def compute_match_score(face_sim: float, time_diff_days: float, location_sim: float) -> float:
        """
        Intelligence Layer: Computes a weighted match score.
        70% Face Similarity + 20% Time Context + 10% Location Context.
        """
        # Time score: decay over time (e.g., 1.0 at 0 days, 0.5 at 30 days)
        time_score = max(0.0, 1.0 - (time_diff_days / 60.0)) 
        
        # Combined weighted score
        return (0.7 * face_sim) + (0.2 * time_score) + (0.1 * location_sim)
    
    def __init__(self):
        """Initialize the face search service with CV pipeline and vector DB."""
        self.pipeline = FaceCVPipeline()
        self.vdb = VectorDB()
        self.age_gan = AgeProgressionGAN()
        
    def index_image(self, image_path: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Processes an image, extracts embeddings, and stores them in the vector database.
        
        Args:
            image_path: Path to the image file
            metadata: Optional metadata to store with the embeddings
            
        Returns:
            Dictionary with indexing status and results
        """
        import os
        try:
            results = self.pipeline.process_image(image_path)
            
            if not results:
                return {"status": "success", "faces_found": 0}
                
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
                
            success = self.vdb.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas)
            
            if success:
                # Event-driven matching: Trigger cross-match for each new face
                status_str = metadata.get("status", "unknown")
                if status_str in ["missing", "found"]:
                    for emb in embeddings:
                        self.match_on_insert(emb, status_str, metadata)
                
                return {"status": "success", "faces_found": len(results), "ids": ids}
            else:
                return {"status": "error", "message": "Failed to upsert embeddings to vector DB"}
                
        except Exception as e:
            logger.error(f"Error indexing image {image_path}: {e}")
            raise e

    def match_on_insert(self, embedding: List[float], status: str, metadata: Dict[str, Any]):
        """
        Matching logic triggered on new post insertion.
        Searches ALL people to find similarities, but only alerts on cross-status matches.
        """
        
        # 1. Search Vector DB (NO status filter here to allow finding duplicates or same-status matches)
        results = self.vdb.search(
            query_embedding=embedding,
            n_results=10
        )
        
        if not results or not results.get("ids") or not results["ids"][0]:
            return
            
        # 2. Process matches
        ids = results["ids"][0]
        distances = results["distances"][0]
        metadatas = results["metadatas"][0]
        
        current_post_id = metadata.get("postId")
        current_loc = metadata.get("location")
        
        for i in range(len(ids)):
            match_meta = metadatas[i]
            match_post_id = match_meta.get("postId")
            match_status = match_meta.get("status", "unknown").lower()
            
            if not current_post_id or not match_post_id or current_post_id == match_post_id:
                continue
                
            # Improved Similarity Mapping: 0.6 distance -> ~70% similarity
            # Using a scale where 0.8 distance is the "limit" of identity
            face_sim = max(0.0, 1.0 - (distances[i] / 0.8))
            
            loc_sim = 1.0 if current_loc and current_loc == match_meta.get("location") else 0.0
            
            # Compute intelligence score
            combined_score = self.compute_match_score(face_sim, 0.0, loc_sim)
            
            # 3. Alerting Logic (Cross-Status Only)
            is_cross_match = (status == "missing" and match_status == "found") or \
                             (status == "found" and match_status == "missing")
            
            if is_cross_match and combined_score > 0.40: # Lowered threshold slightly for better recall
                # Deduplication Layer
                p1, p2 = (current_post_id, match_post_id) if status == "missing" else (match_post_id, current_post_id)
                
                try:
                    FaceMatch.objects.create(
                        missing_post_id=p1,
                        found_post_id=p2,
                        combined_score=combined_score,
                        face_similarity=face_sim,
                        time_score=1.0, 
                        location_score=loc_sim
                    )
                    
                    # Trigger Webhook
                    match_data = {
                        "missing_post_id": p1,
                        "found_post_id": p2,
                        "score": combined_score,
                        "metadata": match_meta
                    }
                    WebhookNotifier.send_high_confidence_match_alert(match_data)
                except Exception:
                    pass
            
    def _apply_weighting_and_webhooks(self, search_res: Dict[str, Any], query_metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Applies Geospatial and Status weighting to the raw vector DB similarity scores.
        Triggers Webhooks on High Confidence Matches.
        """
        if not search_res or not search_res.get("ids") or not search_res["ids"] or not search_res["ids"][0]:
            return []
            
        enhanced_results = []
        ids = search_res["ids"][0]
        distances = search_res["distances"][0]
        metadatas = search_res["metadatas"][0]
        
        for i in range(len(ids)):
            face_id = ids[i]
            dist = distances[i]
            meta = metadatas[i]
            
            # Improved Similarity Mapping: 0.6 distance -> ~70% similarity
            # Using a scale where 0.8 distance is the "limit" of identity
            similarity = round(100 * max(0.0, 1.0 - (dist / 0.8)), 1)
            
            # --- START WEIGHTING LOGIC ---
            if query_metadata:
                db_status = meta.get("status", "unknown").lower()
                query_status = query_metadata.get("status", "unknown").lower()
                
                # Cross-matching missing and found: boost score slightly
                if (query_status == "missing" and db_status == "found") or (query_status == "found" and db_status == "missing"):
                    similarity += 5.0
                    
                db_loc = meta.get("location")
                query_loc = query_metadata.get("location")
                if db_loc and query_loc and db_loc == query_loc:
                     similarity += 5.0
                     
            similarity = min(similarity, 99.9)
            # --- END WEIGHTING LOGIC ---
            
            match_data = {
                "id": face_id,
                "distance": dist,
                "similarity": similarity,
                "metadata": meta
            }
            enhanced_results.append(match_data)
            
            # --- START WEBHOOK LOGIC ---
            if similarity >= 95.0:
                 WebhookNotifier.send_high_confidence_match_alert(match_data)
            # --- END WEBHOOK LOGIC ---
            
        enhanced_results.sort(key=lambda x: x["similarity"], reverse=True)
        return enhanced_results

    def search_faces_in_frame(self, frame_path: str, n_results: int = 1, query_metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Searches for all faces in a given frame/image.
        Returns a list of dictionaries containing bounding box, score, and match details.
        
        Args:
            frame_path: Path to the frame image
            n_results: Number of results to return per face
            
        Returns:
            List of detected faces and their matches
        """
        try:
            results = self.pipeline.process_image(frame_path)
            detections = []
            
            for face in results:
                search_res = self.vdb.search(query_embedding=face.embedding, n_results=n_results)
                
                enhanced = self._apply_weighting_and_webhooks(search_res, query_metadata=query_metadata)
                match = enhanced[0] if enhanced else None
                
                detections.append({
                    "bbox": face.bbox,
                    "score": face.score,
                    "match": match
                })
                
            return detections
        except Exception as e:
            logger.error(f"Error searching faces in frame: {e}")
            return []
    
    def search_face_by_image(
        self,
        image_path: str,
        n_results: int = 5,
        cleanup: bool = True,
        query_metadata: Optional[Dict[str, Any]] = None,
        use_age_progression: bool = False
    ) -> Dict[str, Any]:
        """
        Search for similar faces in the vector database using an image.
        
        Args:
            image_path: Path to the image file
            n_results: Number of results to return (default: 5)
            cleanup: Whether to cleanup the temp image file after processing (default: True)
            use_age_progression: If true, generates +5, +10, +15 aged images and searches them too.
            
        Returns:
            Dictionary with search status and results
        """
        try:
            images_to_process = [image_path]
            aged_paths = {}
            
            if use_age_progression:
                # Generate aged variations (e.g., +5, +10, +15 years)
                aged_paths = self.age_gan.generate_aged_images(image_path, age_jumps=[5, 10, 15])
                images_to_process.extend(list(aged_paths.values()))

            all_search_results = {"ids": [[]], "distances": [[]], "metadatas": [[]]}
            total_faces_detected = 0
            
            # Keep track of best distance for each face ID to deduplicate results
            best_matches = {}

            for current_img_path in images_to_process:
                # Process image synchronously to extract face embeddings
                results = self.pipeline.process_image(current_img_path)
                
                if results:
                    total_faces_detected += len(results)
                    query_embedding = results[0].embedding
                    
                    # Search in vector database
                    search_results = self.vdb.search(query_embedding=query_embedding, n_results=n_results)
                    
                    # Aggregate results to find best matches across all age jumps
                    if search_results and search_results.get("ids") and search_results["ids"][0]:
                        ids = search_results["ids"][0]
                        dists = search_results["distances"][0]
                        metas = search_results["metadatas"][0]
                        
                        for idx, face_id in enumerate(ids):
                            if face_id not in best_matches or dists[idx] < best_matches[face_id]["dist"]:
                                best_matches[face_id] = {
                                    "dist": dists[idx],
                                    "meta": metas[idx]
                                }
                
                # Cleanup temp aged files immediately
                if current_img_path != image_path:
                    cleanup_temp_file(current_img_path)
                    
            # Cleanup original temp file if requested
            if cleanup:
                cleanup_temp_file(image_path)
            
            if total_faces_detected == 0:
                return {
                    "status": "success",
                    "results": [],
                    "message": "No faces detected in image or its age progressions."
                }
                
            # Reconstruct the aggregated search results dictionary for the weighting step
            for face_id, data in best_matches.items():
                all_search_results["ids"][0].append(face_id)
                all_search_results["distances"][0].append(data["dist"])
                all_search_results["metadatas"][0].append(data["meta"])
            
            # Weight results and trigger Webhooks
            enhanced_results = self._apply_weighting_and_webhooks(all_search_results, query_metadata=query_metadata)
            
            # Sort final output again by similarity
            enhanced_results = sorted(enhanced_results, key=lambda x: x["similarity"], reverse=True)[:n_results]
            
            return {
                "status": "success",
                "search_results": enhanced_results,
                "faces_detected": total_faces_detected,
                "used_age_progression": use_age_progression
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
        n_results: int = 5,
        query_metadata: Optional[Dict[str, Any]] = None
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
                result = self.search_face_by_image(
                    image_path, 
                    n_results=n_results, 
                    cleanup=True,
                    query_metadata=query_metadata
                )
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

    def get_people_by_status(self, status: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve people by their status (missing/found)."""
        results = self.vdb.get_vectors(where={"status": status}, limit=limit, offset=offset)
        
        people = []
        if not results or not results.get("ids"):
            return people
            
        for i in range(len(results["ids"])):
            people.append({
                "id": results["ids"][i],
                "metadata": results["metadatas"][i]
            })
        return people

    def cross_match_background(self, batch_size: int = 50):
        """
        Background Reconciliation Job: Iterates through all missing posts
        and searches against found posts to ensure no matches were missed.
        """
        offset = 0
        logger.info(f"Starting background cross-match reconciliation...")
        
        while True:
            # Batch missing posts
            missing_batch = self.vdb.get_vectors(where={"status": "missing"}, limit=batch_size, offset=offset)
            
            if not missing_batch or not missing_batch.get("ids") or len(missing_batch["ids"]) == 0:
                break
                
            ids = missing_batch["ids"]
            embeddings = missing_batch["embeddings"]
            metadatas = missing_batch["metadatas"]
            
            for i in range(len(ids)):
                # Perform the same matching logic as on_insert
                self.match_on_insert(embeddings[i], "missing", metadatas[i])
                
            offset += batch_size
            if len(ids) < batch_size:
                break
        
        logger.info("Background cross-match reconciliation completed.")
