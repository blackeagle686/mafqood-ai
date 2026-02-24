import cv2
import numpy as np
import logging
from typing import List, Dict, Any, Optional
from insightface.app import FaceAnalysis
from app.config import CV_CTX_ID, FACE_ANALYSIS_MODEL
from app.schemas.cv import PipelineResultSchema, FaceDetectionSchema

logger = logging.getLogger(__name__)

# --- Model Loader (Singleton Pattern) ---

class FaceModelLoader:
    """Loads and caches models to avoid reloading on every request."""
    _face_analysis = None

    @classmethod
    def get_face_analysis(cls):
        if cls._face_analysis is None:
            # allow tests or offline environments to skip downloading the model
            if os.getenv("INSIGHTFACE_OFFLINE") == "1":
                logger.info("INSIGHTFACE_OFFLINE=1; using dummy face analysis")
                class _Dummy:
                    def prepare(self, *args, **kwargs):
                        pass
                    def get(self, image):
                        return []
                cls._face_analysis = _Dummy()
                return cls._face_analysis

            logger.info(f"Loading InsightFace model: {FACE_ANALYSIS_MODEL} (ctx_id={CV_CTX_ID})")
            try:
                cls._face_analysis = FaceAnalysis(name=FACE_ANALYSIS_MODEL)
                if cls._face_analysis:
                    cls._face_analysis.prepare(ctx_id=CV_CTX_ID, det_size=(640, 640))
                else:
                    raise RuntimeError("Failed to create FaceAnalysis instance.")
            except Exception as e:
                logger.error(f"Failed to load InsightFace model: {e}")
                raise
        return cls._face_analysis

# --- Pipeline Orchestrator ---

class FaceCVPipeline:
    def __init__(self):
        self.app = FaceModelLoader.get_face_analysis()

    def process_image(self, image_path: str) -> List[PipelineResultSchema]:
        """Processes an image and returns a list of validated PipelineResultSchema."""
        logger.info(f"Processing image: {image_path}")
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"Could not read image at {image_path}")
            return []

        try:
            # Step 1: Detect and Extract (One-step via InsightFace)
            # This returns a list of face objects with bbox, kps, embedding, etc.
            faces = self.app.get(image)
            results = []

            for face in faces:
                bbox = face.bbox.astype(int).tolist()
                
                # Minimum size check (User suggestion integrated)
                x1, y1, x2, y2 = bbox
                w_face = x2 - x1
                h_face = y2 - y1
                
                if w_face < 40 or h_face < 40:
                    logger.warning(f"Face too small ({w_face}x{h_face}), skipping.")
                    continue

                if face.embedding is not None:
                    results.append(PipelineResultSchema(
                        bbox=bbox,
                        embedding=face.embedding.tolist(),
                        score=float(face.det_score)
                    ))

            logger.info(f"Pipeline finished. Found {len(results)} faces.")
            return results
        except Exception as e:
            logger.error(f"Error in CV pipeline processing: {e}")
            return []

# For Backward Compatibility
def run_pipeline(image_path: str) -> List[PipelineResultSchema]:
    pipeline = FaceCVPipeline()
    return pipeline.process_image(image_path)
