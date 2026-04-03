from services.face_search_service import FaceSearchService
from services.cv_service import FaceCVPipeline

class SearchPipeline:
    def __init__(self):
        self.face_search_service = FaceSearchService()
        self.cv_pipeline = FaceCVPipeline()

    def execute(self, image_path: str, **kwargs):
        # Implementation logic moved from services or coordinated here
        return self.face_search_service.search_face_by_image(image_path, **kwargs)
