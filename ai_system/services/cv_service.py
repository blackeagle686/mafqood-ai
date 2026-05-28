import cv2
import numpy as np
import logging
from typing import List, Dict, Any, Optional
import os
from insightface.app import FaceAnalysis
from app.config import CV_CTX_ID, FACE_ANALYSIS_MODEL
# Use core entities instead of schemas if possible, or keep schemas for now
from core.entities import Face 

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

    def enhance_image(self, image: np.ndarray) -> np.ndarray:
        """
        Enhances image quality to improve face detection for challenging conditions:
        - Denoising for low-quality/grainy images
        - Dynamic Gamma Correction for poor lighting (dark/overexposed)
        - Unsharp Masking for better edge definition (glasses, facial contours)
        """
        # 1. Denoise to handle grainy/noisy images
        # We use a relatively light filter to preserve facial textures
        denoised = cv2.fastNlMeansDenoisingColored(image, None, 5, 5, 7, 21)

        # 2. Dynamic Gamma Correction for lighting
        # Calculate mean brightness (L channel in LAB)
        lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        mean_brightness = np.mean(l)

        # Target a mean brightness of ~130
        gamma = 1.0
        if mean_brightness < 90:  # Very dark
            gamma = 1.5
        elif mean_brightness > 180:  # Overexposed
            gamma = 0.8
            
        if gamma != 1.0:
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
            l_gamma = cv2.LUT(l, table)
            lab = cv2.merge((l_gamma, a, b))
            color_corrected = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        else:
            color_corrected = denoised

        # 3. Mild Unsharp Masking to define edges (helps with glasses)
        gaussian = cv2.GaussianBlur(color_corrected, (0, 0), 2.0)
        enhanced = cv2.addWeighted(color_corrected, 1.3, gaussian, -0.3, 0)

        return enhanced

    def process_image(self, image_path: str) -> List[Face]:
        """Processes an image and returns a list of validated PipelineResultSchema."""
        logger.info(f"Processing image: {image_path}")
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"Could not read image at {image_path}")
            return []

        try:
            # Apply enhancement to handle noise, lighting, and glasses
            processed_img = self.enhance_image(image)

            # Step 1: Detect and Extract (One-step via InsightFace)
            # This returns a list of face objects with bbox, kps, embedding, etc.
            faces = self.app.get(processed_img)
            results = []

            for face in faces:
                bbox = face.bbox.astype(int).tolist()
                
                # Minimum size check (User suggestion integrated)
                x1, y1, x2, y2 = bbox
                w_face = x2 - x1
                h_face = y2 - y1
                
                if w_face < 20 or h_face < 20:
                    logger.warning(f"Face too small ({w_face}x{h_face}), skipping.")
                    continue

                if face.embedding is not None:
                    results.append(Face(
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
def run_pipeline(image_path: str) -> List[Face]:
    pipeline = FaceCVPipeline()
    return pipeline.process_image(image_path)
