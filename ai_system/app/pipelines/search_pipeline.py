import cv2
import os
import uuid
import logging
from services.face_search_service import FaceSearchService
from services.cv_service import FaceCVPipeline
from utils.file_utils import cleanup_temp_file

logger = logging.getLogger(__name__)

class SearchPipeline:
    def __init__(self):
        self.face_search_service = FaceSearchService()
        self.cv_pipeline = FaceCVPipeline()

    def execute(self, file_path: str, **kwargs):
        # Detection of video files
        if file_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
            return self.execute_video(file_path, **kwargs)
        return self.face_search_service.search_face_by_image(file_path, **kwargs)

    def execute_video(self, video_path: str, n_results: int = 5, sampling_rate: int = 15, **kwargs):
        logger.info(f"Processing video: {video_path} with sampling_rate: {sampling_rate}")
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"status": "error", "message": "Failed to open video file"}

        all_matches = {}
        frame_count = 0
        total_faces = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_count % sampling_rate == 0:
                    # Save frame temporarily
                    temp_frame_path = os.path.join("temp_uploads", f"frame_{uuid.uuid4()}.jpg")
                    cv2.imwrite(temp_frame_path, frame)
                    
                    # Search in frame
                    res = self.face_search_service.search_face_by_image(
                        temp_frame_path, 
                        n_results=n_results,
                        cleanup=True,
                        **kwargs
                    )
                    
                    if res["status"] == "success":
                        hits = res.get("search_results", [])
                        total_faces += res.get("faces_detected", 0)
                        for hit in hits:
                            face_id = hit["id"]
                            # Deduplicate and keep best hit per person using similarity
                            if face_id not in all_matches or hit["similarity"] > all_matches[face_id]["similarity"]:
                                all_matches[face_id] = hit

                frame_count += 1
        finally:
            cap.release()
            cleanup_temp_file(video_path)

        # Sort aggregated results by similarity
        sorted_results = sorted(all_matches.values(), key=lambda x: x["similarity"], reverse=True)[:n_results]
        
        return {
            "status": "success",
            "search_results": sorted_results,
            "total_frames_processed": frame_count // sampling_rate,
            "total_faces_detected": total_faces
        }
