import sys
import os
from unittest.mock import MagicMock

# Mock cv2 and insightface before they are imported by anything else
sys.modules['cv2'] = MagicMock()
sys.modules['insightface'] = MagicMock()
sys.modules['insightface.app'] = MagicMock()

import django
import pytest
from unittest.mock import patch, MagicMock

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mafqood_project.settings')
os.environ.setdefault('INSIGHTFACE_OFFLINE', '1')
django.setup()

from rest_framework.test import APIClient
from django.test import TestCase

class TestMatchPostEndpoint(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/ai/match-post/'
        
    @patch('app.ai.views._get_face_service')
    @patch('os.path.exists')
    def test_match_post_happy_path(self, mock_exists, mock_get_face):
        # Mock file existence
        mock_exists.return_value = True
        
        # Mock Search results
        mock_face_service = MagicMock()
        mock_face_service.search_face_by_image.return_value = {
            "status": "success",
            "search_results": [
                {
                    "id": "face_405_0",
                    "similarity": 96.0,
                    "metadata": {"postId": 405}
                },
                {
                    "id": "face_218_0",
                    "similarity": 82.0,
                    "metadata": {"post_id": 218}
                }
            ]
        }
        mock_get_face.return_value = mock_face_service
        
        payload = {
            "postId": 15,
            "userId": "0198e260-1145-79be-a3d9-2e6f1ad0a7dd",
            "imageUrl": "/uploads/images/some-image-name.jpg",
            "postType": 0
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        assert response.status_code == 200
        data = response.json()
        assert data["isSuccess"] is True
        assert data["hasData"] is True
        assert data["data"]["postId"] == 15
        assert len(data["data"]["matches"]) == 2
        assert data["data"]["matches"][0]["matchedPostId"] == 405
        assert data["data"]["matches"][0]["confidenceScore"] == 0.96
        assert data["data"]["matches"][1]["matchedPostId"] == 218
        assert data["data"]["matches"][1]["confidenceScore"] == 0.82

    def test_match_post_invalid_input(self):
        payload = {
            "postId": "not-an-int",
            "userId": "0198e260-1145-79be-a3d9-2e6f1ad0a7dd",
            "imageUrl": "/uploads/images/some-image-name.jpg",
            "postType": 0
        }
        response = self.client.post(self.url, payload, format='json')
        assert response.status_code == 400
        assert response.json()["isSuccess"] is False

    @patch('os.path.exists')
    def test_match_post_image_not_found(self, mock_exists):
        mock_exists.return_value = False
        payload = {
            "postId": 15,
            "userId": "0198e260-1145-79be-a3d9-2e6f1ad0a7dd",
            "imageUrl": "/uploads/images/missing.jpg",
            "postType": 0
        }
        response = self.client.post(self.url, payload, format='json')
        assert response.status_code == 404
        assert response.json()["isSuccess"] is False

    @patch('app.ai.views.download_remote_image')
    @patch('app.ai.views.cleanup_temp_file')
    @patch('app.ai.views._get_face_service')
    def test_match_post_remote_url(self, mock_get_face, mock_cleanup, mock_download):
        # Mock download
        mock_download.return_value = "/tmp/remote_image.jpg"
        
        # Mock Search results
        mock_face_service = MagicMock()
        mock_face_service.search_face_by_image.return_value = {
            "status": "success",
            "search_results": [{"id": "face_1", "similarity": 90.0, "metadata": {"postId": 101}}]
        }
        mock_get_face.return_value = mock_face_service
        
        payload = {
            "postId": 15,
            "userId": "user1",
            "imageUrl": "https://example.com/photo.jpg",
            "postType": 0
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        assert response.status_code == 200
        assert mock_download.called_once_with("https://example.com/photo.jpg")
        assert mock_cleanup.called_once_with("/tmp/remote_image.jpg")
        assert response.json()["isSuccess"] is True

if __name__ == "__main__":
    pytest.main([__file__])
