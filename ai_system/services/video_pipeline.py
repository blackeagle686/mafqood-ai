import cv2
import os
import logging
from typing import List, Dict, Any, Optional
from services.face_search_service import FaceSearchService
from utils.file_utils import cleanup_temp_file

logger = logging.getLogger(__name__)

class VideoProcessor:
    """
    Service responsible for handling video files, sampling frames,
    and performing face recognition on those frames.
    """
    
    def __init__(self, sampling_rate: int = 15):
        """
        Initialize with a sampling rate.
        sampling_rate: Process every Nth frame.
        """
        self.sampling_rate = sampling_rate
        self.face_search = FaceSearchService()

    def process_video(self, video_path: str) -> List[Dict[str, Any]]:
        """
        Opens a video file, iterates through frames at the sampling rate,
        and searches for faces in each sampled frame.
        """
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return []

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Failed to open video file: {video_path}")
            return []

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        logger.info(f"Processing video {video_path}: {total_frames} frames, {fps} FPS, sampling every {self.sampling_rate} frames")

        all_detections = []
        frame_idx = 0
        
        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % self.sampling_rate == 0:
                    # Save frame temporarily to process it
                    # (Improving memory efficiency by not keeping all frames in memory)
                    os.makedirs("temp_uploads", exist_ok=True)
                    temp_frame_path = os.path.join("temp_uploads", f"vframe_{frame_idx}.jpg")
                    cv2.imwrite(temp_frame_path, frame)
                    
                    try:
                        # Search for all faces in this specific frame
                        detections = self.face_search.search_faces_in_frame(temp_frame_path, n_results=1)
                        
                        if detections:
                            # Filter for detections that actually have a match
                            matches = [d for d in detections if d.get("match")]
                            if matches:
                                all_detections.append({
                                    "frame": frame_idx,
                                    "timestamp": round(frame_idx / fps, 2) if fps > 0 else 0,
                                    "matches": matches
                                })
                    except Exception as e:
                        logger.error(f"Error processing frame {frame_idx}: {e}")
                    finally:
                        # Cleanup temp frame immediately
                        cleanup_temp_file(temp_frame_path)
                
                frame_idx += 1
                
        except Exception as e:
            logger.error(f"Unexpected error during video processing: {e}")
        finally:
            cap.release()
            
        logger.info(f"Video processing finished. Found matches in {len(all_detections)} frames.")
        return all_detections
