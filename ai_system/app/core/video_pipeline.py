import cv2
import logging
import os
from typing import List, Dict, Any, Optional
from app.core.face_search_service import FaceSearchService
from app.schemas.cv import SearchResultSchema

logger = logging.getLogger(__name__)

class VideoProcessor:
    """Processes video files to detect and search for faces."""

    def __init__(self, sampling_rate: int = 1):
        """
        Args:
            sampling_rate: Number of frames to skip before processing the next one.
                           If sampling_rate=1, process every frame.
                           If video is 30fps and sampling_rate=30, process 1 frame per second.
        """
        self.sampling_rate = sampling_rate
        self.search_service = FaceSearchService()

    def process_video(self, video_path: str) -> List[Dict[str, Any]]:
        """
        Reads video and searches for faces in sampled frames.
        Returns a list of detections with timestamps and search results.
        """
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return []

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Could not open video: {video_path}")
            return []

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        logger.info(f"Processing video: {video_path} ({fps} FPS, {total_frames} frames)")

        results = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % self.sampling_rate == 0:
                timestamp = frame_idx / fps
                logger.info(f"Processing frame {frame_idx} at {timestamp:.2f}s")

                # Save frame temporarily for pipeline (or modify pipeline to accept array)
                # For now, let's use a temporary file to keep FaceCVPipeline as is
                temp_frame_path = f"temp_frame_{frame_idx}.jpg"
                cv2.imwrite(temp_frame_path, frame)
                
                try:
                    detections = self.search_service.search_faces_in_frame(temp_frame_path, n_results=1)
                    
                    for det in detections:
                        results.append({
                            "timestamp": timestamp,
                            "frame_idx": frame_idx,
                            "bbox": det["bbox"],
                            "score": det["score"],
                            "match": det["match"]
                        })
                finally:
                    if os.path.exists(temp_frame_path):
                        os.remove(temp_frame_path)

            frame_idx += 1

        cap.release()
        logger.info(f"Video processing finished. Found {len(results)} potential face instances.")
        return results
