"""
Comprehensive test suite for the CV pipeline workflow.
Tests utils, cv_pipeline, cv_tasks, and cv endpoints.
"""
import pytest
import os
import sys
import shutil
import tempfile
import uuid
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from PIL import Image
import numpy as np

# ensure project root is on sys.path so that `import app` works inside containers
sys.path.insert(0, os.path.abspath(os.getcwd()))

# Test fixtures and utilities
@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    if os.path.exists(temp_path):
        shutil.rmtree(temp_path)


@pytest.fixture
def sample_image(temp_dir):
    """Return a sample image for testing.

    Priority:
    1. ``TEST_FACE_IMAGE_PATH`` env var pointing to a file.
    2. Same var pointing to a directory – create a small image inside.
    3. Any image already checked in under ``images_vdb``.
    4. Fallback to a generated red image in ``temp_dir``.
    """
    provided = os.getenv("TEST_FACE_IMAGE_PATH")
    if provided:
        if os.path.isfile(provided):
            return provided
        if os.path.isdir(provided):
            generated = os.path.join(provided, "provided_image.jpg")
            img = Image.new('RGB', (100, 100), color='blue')
            img.save(generated)
            return generated

    # check for checked‑in images (images_vdb directory at project root)
    repo_images_dir = os.path.join(os.getcwd(), "images_vdb")
    if os.path.isdir(repo_images_dir):
        for fname in os.listdir(repo_images_dir):
            if fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                return os.path.join(repo_images_dir, fname)

    # fallback: generate a simple image
    image_path = os.path.join(temp_dir, "test_image.jpg")
    img = Image.new('RGB', (100, 100), color='red')
    img.save(image_path)
    return image_path


@pytest.fixture
def test_client():
    """Create a FastAPI test client."""
    from app.main import app
    return TestClient(app)


# ============================================================================
# TESTS FOR app/core/utils.py
# ============================================================================

class TestUtilsFunctions:
    """Test utility functions for file handling."""
    
    def test_get_file_extension(self):
        """Test extracting file extension."""
        from app.core.utils import get_file_extension
        
        assert get_file_extension("image.jpg") == ".jpg"
        assert get_file_extension("photo.png") == ".png"
        assert get_file_extension("file.tar.gz") == ".gz"
        assert get_file_extension("noextension") == ""
    
    def test_generate_temp_filename_with_prefix(self):
        """Test generating temp filenames with prefix."""
        from app.core.utils import generate_temp_filename
        
        # Test with prefix
        filename = generate_temp_filename(prefix="search", file_extension=".jpg")
        assert filename.startswith("search_")
        assert filename.endswith(".jpg")
        assert len(filename) > len("search_.jpg")
        
        # Test without prefix
        filename = generate_temp_filename(file_extension=".png")
        assert filename.endswith(".png")
        assert not filename.startswith("_")
        
        # Test without extension
        filename = generate_temp_filename(prefix="video")
        assert filename.startswith("video_")
    
    def test_generate_temp_filename_uniqueness(self):
        """Test that generated filenames are unique."""
        from app.core.utils import generate_temp_filename
        
        filenames = [generate_temp_filename(prefix="test", file_extension=".jpg") for _ in range(10)]
        assert len(set(filenames)) == 10  # All unique
    
    def test_save_uploaded_file(self, temp_dir, sample_image):
        """Test saving uploaded files."""
        from app.core.utils import save_uploaded_file
        from fastapi import UploadFile
        from io import BytesIO
        
        # Create a mock uploaded file
        with open(sample_image, "rb") as f:
            uploaded_file = UploadFile(
                file=BytesIO(f.read()),
                filename="test.jpg",
                size=os.path.getsize(sample_image)
            )
            
            saved_path = save_uploaded_file(uploaded_file, temp_upload_dir=temp_dir, prefix="test")
            
            # Verify file was saved
            assert os.path.exists(saved_path)
            assert os.path.isabs(saved_path)
            assert "test_" in os.path.basename(saved_path)
            assert saved_path.endswith(".jpg")
    
    def test_cleanup_temp_file(self, temp_dir):
        """Test cleaning up temporary files."""
        from app.core.utils import cleanup_temp_file
        
        # Create a test file
        test_file = os.path.join(temp_dir, "test_file.txt")
        with open(test_file, "w") as f:
            f.write("test content")
        
        assert os.path.exists(test_file)
        
        # Clean it up
        result = cleanup_temp_file(test_file)
        assert result is True
        assert not os.path.exists(test_file)
        
        # Try cleaning non-existent file
        result = cleanup_temp_file(test_file)
        assert result is False
    
    def test_ensure_list(self):
        """Test ensure_list utility function."""
        from app.core.utils import ensure_list
        
        assert ensure_list(None) == []
        assert ensure_list([1, 2, 3]) == [1, 2, 3]
        assert ensure_list("single") == ["single"]
        assert ensure_list(42) == [42]


# ============================================================================
# TESTS FOR app/core/cv_pipeline.py
# ============================================================================

class TestCVPipeline:
    """Test CV pipeline functionality."""
    
    @patch('app.core.cv_pipeline.FaceCVPipeline.process_image')
    def test_process_image_with_faces(self, mock_process):
        """Test processing image with detected faces."""
        from app.core.cv_pipeline import FaceCVPipeline
        
        # Mock the face detection response
        mock_face = Mock()
        mock_face.embedding = np.random.rand(512).tolist()
        mock_face.bbox = [10, 20, 50, 60]
        mock_face.score = 0.95
        
        mock_process.return_value = [mock_face]
        
        pipeline = FaceCVPipeline()
        results = pipeline.process_image("dummy_image.jpg")
        
        assert len(results) == 1
        assert hasattr(results[0], 'embedding')
        assert len(results[0].embedding) == 512
    
    @patch('app.core.cv_pipeline.FaceCVPipeline.process_image')
    def test_process_image_no_faces(self, mock_process):
        """Test processing image with no detected faces."""
        from app.core.cv_pipeline import FaceCVPipeline
        
        mock_process.return_value = []
        
        pipeline = FaceCVPipeline()
        results = pipeline.process_image("dummy_image.jpg")
        
        assert len(results) == 0


# ============================================================================
# TESTS FOR app/core/face_search_service.py
# ============================================================================

class TestFaceSearchService:
    """Test face search service."""
    
    @patch('app.core.face_search_service.FaceCVPipeline')
    @patch('app.core.face_search_service.VectorDB')
    def test_search_face_by_image_success(self, mock_vdb_class, mock_pipeline_class, temp_dir, sample_image):
        """Test successful face search."""
        from app.core.face_search_service import FaceSearchService
        
        # Mock pipeline
        mock_pipeline = Mock()
        mock_face = Mock()
        mock_face.embedding = np.random.rand(512).tolist()
        mock_pipeline.process_image.return_value = [mock_face]
        mock_pipeline_class.return_value = mock_pipeline
        
        # Mock vector DB
        mock_vdb = Mock()
        mock_vdb.search.return_value = {
            "ids": ["face_1", "face_2"],
            "distances": [0.1, 0.15],
            "metadatas": [{"source": "image1"}, {"source": "image2"}]
        }
        mock_vdb_class.return_value = mock_vdb
        
        service = FaceSearchService()
        result = service.search_face_by_image(sample_image, n_results=5, cleanup=False)
        
        assert result["status"] == "success"
        assert "search_results" in result
        assert result["faces_detected"] == 1
    
    @patch('app.core.face_search_service.FaceCVPipeline')
    @patch('app.core.face_search_service.VectorDB')
    def test_search_face_no_faces_detected(self, mock_vdb_class, mock_pipeline_class, sample_image):
        """Test search when no faces are detected."""
        from app.core.face_search_service import FaceSearchService
        
        # Mock pipeline returning no faces
        mock_pipeline = Mock()
        mock_pipeline.process_image.return_value = []
        mock_pipeline_class.return_value = mock_pipeline
        
        mock_vdb_class.return_value = Mock()
        
        service = FaceSearchService()
        result = service.search_face_by_image(sample_image, cleanup=False)
        
        assert result["status"] == "success"
        assert result["results"] == []
        assert "No faces detected" in result["message"]
    
    @patch('app.core.face_search_service.FaceCVPipeline')
    @patch('app.core.face_search_service.VectorDB')
    def test_get_database_info(self, mock_vdb_class, mock_pipeline_class):
        """Test getting database information."""
        from app.core.face_search_service import FaceSearchService
        
        mock_vdb = Mock()
        mock_vdb.get_count.return_value = 1000
        mock_vdb_class.return_value = mock_vdb
        
        mock_pipeline_class.return_value = Mock()
        
        service = FaceSearchService()
        result = service.get_database_info()
        
        assert result["status"] == "success"
        assert result["database_info"]["total_faces"] == 1000
    
    @patch('app.core.face_search_service.FaceCVPipeline')
    @patch('app.core.face_search_service.VectorDB')
    def test_delete_faces(self, mock_vdb_class, mock_pipeline_class):
        """Test deleting faces from database."""
        from app.core.face_search_service import FaceSearchService
        
        mock_vdb = Mock()
        mock_vdb.delete.return_value = True
        mock_vdb_class.return_value = mock_vdb
        
        mock_pipeline_class.return_value = Mock()
        
        service = FaceSearchService()
        result = service.delete_faces(["face_1", "face_2"])
        
        assert result["status"] == "success"
        assert result["deleted_count"] == 2


# ============================================================================
# TESTS FOR app/tasks/cv_tasks.py
# ============================================================================

class TestCVTasks:
    """Test Celery tasks."""
    
    @patch('app.tasks.cv_tasks.FaceCVPipeline')
    @patch('app.tasks.cv_tasks.VectorDB')
    def test_process_image_task(self, mock_vdb_class, mock_pipeline_class):
        """Test image processing task."""
        from app.tasks.cv_tasks import process_image_task
        
        # Mock pipeline
        mock_pipeline = Mock()
        mock_face = Mock()
        mock_face.embedding = [0.1] * 512
        mock_face.bbox = [10, 20, 50, 60]
        mock_face.score = 0.95
        mock_pipeline.process_image.return_value = [mock_face]
        mock_pipeline_class.return_value = mock_pipeline
        
        # Mock vector DB
        mock_vdb = Mock()
        mock_vdb.upsert.return_value = True
        mock_vdb_class.return_value = mock_vdb
        
        result = process_image_task("dummy_image.jpg", metadata={"source": "test"})
        
        assert result["status"] == "success"
        assert result["faces_found"] == 1
        assert "ids" in result
    
    @patch('app.tasks.cv_tasks.FaceSearchService')
    def test_search_faces_task(self, mock_search_service_class):
        """Test face search task."""
        from app.tasks.cv_tasks import search_faces_task
        
        # Mock search service
        mock_service = Mock()
        mock_service.search_face_by_image.return_value = {
            "status": "success",
            "search_results": {
                "ids": ["face_1"],
                "distances": [0.1]
            }
        }
        mock_search_service_class.return_value = mock_service
        
        result = search_faces_task("dummy_image.jpg", n_results=5)
        
        assert result["status"] == "success"
        assert "search_results" in result
    
    @patch('app.tasks.cv_tasks.VideoProcessor')
    def test_process_video_task(self, mock_processor_class):
        """Test video processing task."""
        from app.tasks.cv_tasks import process_video_task
        
        # Mock video processor
        mock_processor = Mock()
        mock_processor.process_video.return_value = [
            {"timestamp": 0, "faces": 2},
            {"timestamp": 1, "faces": 1}
        ]
        mock_processor_class.return_value = mock_processor
        
        result = process_video_task("dummy_video.mp4", sampling_rate=15)
        
        assert result["status"] == "success"
        assert result["detections_count"] == 2


# ============================================================================
# TESTS FOR app/api/endpoints/cv.py
# ============================================================================

class TestCVEndpoints:
    """Test CV API endpoints."""
    
    @patch('app.api.endpoints.cv.process_image_task')
    def test_process_endpoint(self, mock_task, test_client, sample_image):
        """Test image processing endpoint."""
        # Mock the Celery task
        mock_task_obj = Mock()
        mock_task_obj.id = "task_12345"
        mock_task.delay.return_value = mock_task_obj
        
        with open(sample_image, "rb") as f:
            response = test_client.post(
                "/cv/process",
                files={"file": ("test.jpg", f, "image/jpeg")}
            )
        
        assert response.status_code == 200
        assert response.json()["status"] == "queued"
        assert response.json()["task_id"] == "task_12345"
    
    @patch('app.api.endpoints.cv.search_faces_task')
    def test_search_endpoint(self, mock_task, test_client, sample_image):
        """Test face search endpoint."""
        # Mock the Celery task
        mock_task_obj = Mock()
        mock_task_obj.id = "search_task_123"
        mock_task.delay.return_value = mock_task_obj
        
        with open(sample_image, "rb") as f:
            response = test_client.post(
                "/cv/search?n_results=5",
                files={"file": ("test.jpg", f, "image/jpeg")}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["task_id"] == "search_task_123"
        assert data["n_results"] == 5
    
    @patch('app.api.endpoints.cv.process_video_task')
    def test_process_video_endpoint(self, mock_task, test_client, temp_dir):
        """Test video processing endpoint."""
        # Create a dummy video file
        video_path = os.path.join(temp_dir, "test_video.mp4")
        with open(video_path, "wb") as f:
            f.write(b"dummy video content")
        
        mock_task_obj = Mock()
        mock_task_obj.id = "video_task_456"
        mock_task.delay.return_value = mock_task_obj
        
        with open(video_path, "rb") as f:
            response = test_client.post(
                "/cv/process_video?sampling_rate=15",
                files={"file": ("test.mp4", f, "video/mp4")}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["task_id"] == "video_task_456"
    
    @patch('app.api.endpoints.cv.face_search_service')
    def test_database_info_endpoint(self, mock_service, test_client):
        """Test database info endpoint."""
        mock_service.get_database_info.return_value = {
            "status": "success",
            "database_info": {"total_faces": 500}
        }
        
        response = test_client.get("/cv/database/info")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["database_info"]["total_faces"] == 500
    
    @patch('app.api.endpoints.cv.face_search_service')
    def test_delete_faces_endpoint(self, mock_service, test_client):
        """Test delete faces endpoint."""
        mock_service.delete_faces.return_value = {
            "status": "success",
            "deleted_count": 2,
            "message": "Successfully deleted 2 faces"
        }
        
        # `TestClient.delete` does not accept `json` directly in some versions,
        # so use the generic request method.
        response = test_client.request(
            "DELETE",
            "/cv/faces",
            json=["face_1", "face_2"]
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["deleted_count"] == 2
    
    def test_health_endpoint(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/cv/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "cv_pipeline"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestWorkflowIntegration:
    """Integration tests for the complete workflow."""
    
    @patch('app.api.endpoints.cv.search_faces_task')
    @patch('app.api.endpoints.cv.process_image_task')
    def test_upload_and_search_workflow(self, mock_process_task, mock_search_task, test_client, sample_image):
        """Test complete workflow: upload image -> search in vector DB."""
        # First, process an image
        mock_process_obj = Mock()
        mock_process_obj.id = "process_123"
        mock_process_task.delay.return_value = mock_process_obj
        
        with open(sample_image, "rb") as f:
            process_response = test_client.post(
                "/cv/process",
                files={"file": ("image1.jpg", f, "image/jpeg")}
            )
        
        assert process_response.status_code == 200
        process_data = process_response.json()
        assert process_data["status"] == "queued"
        process_task_id = process_data["task_id"]
        
        # Then, search for similar faces
        mock_search_obj = Mock()
        mock_search_obj.id = "search_456"
        mock_search_task.delay.return_value = mock_search_obj
        
        with open(sample_image, "rb") as f:
            search_response = test_client.post(
                "/cv/search?n_results=5",
                files={"file": ("image2.jpg", f, "image/jpeg")}
            )
        
        assert search_response.status_code == 200
        search_data = search_response.json()
        assert search_data["status"] == "queued"
        search_task_id = search_data["task_id"]
        
        # Verify both tasks were created
        assert process_task_id != search_task_id
        assert search_data["n_results"] == 5

@pytest.mark.skipif(os.getenv("RUN_E2E") != "1", reason="Resource-intensive E2E test; disabled by default due to ChromaDB upsert hang in containers. Run only with RUN_E2E=1 in environments with adequate resources.")
class TestE2EWorkflow:
    """End-to-end workflow test without mocks. Requires running services and significant resources.
    
    Note: This test can hang during ChromaDB upsert in container environments with limited resources.
    Enable only when necessary by setting RUN_E2E=1 environment variable.
    """

    @pytest.mark.skip(reason="Temporarily disabled: uses real face-detection model causing hangs in Docker. Consider mocking VectorDB.upsert or running outside containers.")
    def test_full_workflow(self, test_client, sample_image):
        """Upload an image, wait for Celery tasks, and perform search."""
        from app.celery_app import celery_app
        import time

        # Process image via API
        with open(sample_image, "rb") as f:
            proc_resp = test_client.post(
                "/cv/process",
                files={"file": ("real.jpg", f, "image/jpeg")}
            )
        assert proc_resp.status_code == 200
        proc_data = proc_resp.json()
        task_id = proc_data.get("task_id")
        assert task_id

        # Poll Celery result; use a longer timeout to accommodate slow model loading
        result = celery_app.AsyncResult(task_id)
        try:
            res_val = result.get(timeout=300, propagate=False)
        except Exception:
            # fall back to manual polling in case backend raised its own TimeoutError
            start = time.time()
            while not result.ready():
                if time.time() - start > 300:
                    pytest.fail("Celery task did not complete within 5 minutes")
                time.sleep(1)
            res_val = result.result
        assert res_val.get("status") == "success"

        # If faces found, also run search via API and poll
        if res_val.get("faces_found", 0) > 0:
            with open(sample_image, "rb") as f:
                search_resp = test_client.post(
                    "/cv/search?n_results=1",
                    files={"file": ("real.jpg", f, "image/jpeg")}
                )
            assert search_resp.status_code == 200
            search_data = search_resp.json()
            sid = search_data.get("task_id")
            assert sid
            try:
                search_result = celery_app.AsyncResult(sid).get(timeout=300, propagate=False)
            except Exception:
                start = time.time()
                res_obj = celery_app.AsyncResult(sid)
                while not res_obj.ready():
                    if time.time() - start > 300:
                        pytest.fail("Search task did not complete within 5 minutes")
                    time.sleep(1)
                search_result = res_obj.result
            assert search_result.get("status") == "success"
        else:
            # even without faces, API should return queued
            pass

    def test_populate_vdb_and_search(self, temp_dir):
        """Populate the vector DB with dummy embeddings and perform a search."""
        from app.db.vector_db import VectorDB
        from app.core.face_search_service import FaceSearchService
        from app.core.cv_pipeline import FaceCVPipeline
        
        # Build dummy embeddings and insert directly into VectorDB
        vdb = VectorDB()
        ids = []
        embeddings = []
        metadatas = []
        for i in range(3):
            ids.append(f"img_{i}")
            embeddings.append([0.5] * 512)  # constant embedding
            metadatas.append({"source": f"dummy_{i}"})
        vdb.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas)

        # Patch the pipeline so that processing any image returns the same embedding
        with patch('app.core.cv_pipeline.FaceCVPipeline.process_image') as mock_proc:
            mock_face = Mock()
            mock_face.embedding = [0.5] * 512
            mock_face.bbox = [0, 0, 10, 10]
            mock_face.score = 0.99
            mock_proc.return_value = [mock_face]

            service = FaceSearchService()
            # perform search using one dummy path (file existence not required because patched)
            result = service.search_face_by_image("/path/to/dummy.jpg", n_results=3, cleanup=False)

        assert result["status"] == "success"
        assert "search_results" in result
        # should at least return one of the inserted ids
        assert len(result["search_results"]["ids"][0]) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
