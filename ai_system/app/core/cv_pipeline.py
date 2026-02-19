import cv2
import numpy as np
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from retinaface import RetinaFace
from insightface.app import FaceAnalysis
from app.config import CV_CTX_ID, FACE_ANALYSIS_MODEL

logger = logging.getLogger(__name__)

# --- Interfaces ---

class IFaceDetector(ABC):
    @abstractmethod
    def detect_faces(self, image: np.ndarray) -> List[Dict[str, Any]]:
        return []

class IFaceCropper(ABC):
    @abstractmethod
    def crop(self, image: np.ndarray, bbox: List[int]) -> np.ndarray:
        pass

class IFaceEmbedder(ABC):
    @abstractmethod
    def get_embedding(self, face_image: np.ndarray) -> Optional[np.ndarray]:
        pass

# --- Model Loader (Singleton Pattern) ---

class FaceModelLoader:
    """Loads and caches models to avoid reloading on every request."""
    _face_analysis = None

    @classmethod
    def get_face_analysis(cls):
        if cls._face_analysis is None:
            logger.info(f"Loading InsightFace model: {FACE_ANALYSIS_MODEL} (ctx_id={CV_CTX_ID})")
            try:
                cls._face_analysis = FaceAnalysis(name=FACE_ANALYSIS_MODEL)
                if cls._face_analysis:
                    cls._face_analysis.prepare(ctx_id=CV_CTX_ID)
                else:
                    raise RuntimeError("Failed to create FaceAnalysis instance.")
            except Exception as e:
                logger.error(f"Failed to load InsightFace model: {e}")
                raise
        return cls._face_analysis

# --- Implementations ---

class RetinaFaceDetector(IFaceDetector):
    def detect_faces(self, image: np.ndarray) -> List[Dict[str, Any]]:
        try:
            detections = RetinaFace.detect_faces(image)
            faces = []
            if isinstance(detections, dict):
                for key, val in detections.items():
                    # val["facial_area"] is [x1, y1, x2, y2]
                    faces.append({
                        "id": key,
                        "bbox": val["facial_area"],
                        "score": val.get("score", 0.0)
                    })
            return faces
        except Exception as e:
            logger.error(f"Error in face detection: {e}")
            return []

class OpenCVCropper(IFaceCropper):
    def __init__(self, target_size=(112, 112)):
        self.target_size = target_size

    def crop(self, image: np.ndarray, bbox: List[int]) -> np.ndarray:
        try:
            x1, y1, x2, y2 = bbox
            # Ensure bbox is within image boundaries
            h, w = image.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            
            face = image[y1:y2, x1:x2]
            if face.size == 0:
                return None
                
            face = cv2.resize(face, self.target_size)
            # Convert BGR to RGB if needed (InsightFace expects RGB)
            face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
            return face
        except Exception as e:
            logger.error(f"Error in face cropping: {e}")
            return None

class InsightFaceEmbedder(IFaceEmbedder):
    def __init__(self):
        self.app = FaceModelLoader.get_face_analysis()

    def get_embedding(self, face_image: np.ndarray) -> Optional[np.ndarray]:
        try:
            # InsightFace expects the image to contain the face
            # If we pass a cropped face, it will still run detection on it,
            # which is slightly redundant but safe.
            faces = self.app.get(face_image)
            if not faces:
                return None
            # Return the first detected face's embedding
            return faces[0].embedding
        except Exception as e:
            logger.error(f"Error in embedding extraction: {e}")
            return None

# --- Pipeline Orchestrator ---

class FaceCVPipeline:
    def __init__(self):
        self.detector = RetinaFaceDetector()
        self.cropper = OpenCVCropper()
        self.embedder = InsightFaceEmbedder()

    def process_image(self, image_path: str) -> List[Dict[str, Any]]:
        """Processes an image and returns a list of detected faces with embeddings."""
        logger.info(f"Processing image: {image_path}")
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"Could not read image at {image_path}")
            return []

        # Step 1: Detect Faces
        detections = self.detector.detect_faces(image)
        results = []

        for det in detections:
            bbox = det["bbox"]
            
            # Step 2: Crop Face
            face_crop = self.cropper.crop(image, bbox)
            if face_crop is None:
                continue

            # Step 3: Get Embedding
            embedding = self.embedder.get_embedding(face_crop)
            if embedding is not None:
                results.append({
                    "bbox": bbox,
                    "embedding": embedding.tolist(), # Convert to list for JSON/Storage compatibility
                    "score": det["score"]
                })

        logger.info(f"Pipeline finished. Found {len(results)} faces.")
        return results

# For Backward Compatibility or simple usage
def run_pipeline(image_path: str):
    pipeline = FaceCVPipeline()
    return pipeline.process_image(image_path)
