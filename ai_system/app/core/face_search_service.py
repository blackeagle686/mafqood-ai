"""Service for face search and vector DB operations."""
import logging
from typing import Dict, Any, List, Optional
from app.core.cv_pipeline import FaceCVPipeline
from app.db.vector_db import VectorDB
from app.core.utils import cleanup_temp_file
from app.core.webhook_notifier import WebhookNotifier
from app.core.age_progression import AgeProgressionGAN

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
                return {"status": "success", "faces_found": len(results), "ids": ids}
            else:
                return {"status": "error", "message": "Failed to upsert embeddings to vector DB"}
                
        except Exception as e:
            logger.error(f"Error indexing image {image_path}: {e}")
            raise e
            
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
            
            similarity = round(100 * (1 - dist), 1)
            
            # --- START WEIGHTING LOGIC ---
            if query_metadata:
                db_status = meta.get("status", "unknown").lower()
                query_status = query_metadata.get("status", "unknown").lower()
                
                # Cross-matching missing and found
                if (query_status == "missing" and db_status == "found") or (query_status == "found" and db_status == "missing"):
                    similarity += 3.0
                    
                db_loc = meta.get("location")
                query_loc = query_metadata.get("location")
                # Stub logical distance location check
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
