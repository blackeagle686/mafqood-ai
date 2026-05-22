import sys
import os
import django
import pytest
from unittest.mock import patch, MagicMock
from django.utils import timezone
from datetime import timedelta

# Setup Django settings before importing modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mafqood_project.settings')
os.environ.setdefault('INSIGHTFACE_OFFLINE', '1')
django.setup()

from django.test import TestCase
from rest_framework.test import APIClient
from app.ai.models import Post

class TestLostPostRejectionPolicy(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.posts_url = '/api/ai/posts'
        self.api_key = 'mafqood-shared-secret-key-2026'
        self.client.credentials(HTTP_X_API_KEY=self.api_key)

    @patch('app.ai.views._get_face_service')
    @patch('app.ai.views.download_remote_image')
    def test_post_creation_no_existing_matches_accepted(self, mock_download, mock_get_face):
        mock_download.return_value = 'fake_image.jpg'
        
        mock_face_service = MagicMock()
        mock_face_service.search_face_by_image.return_value = {
            "status": "success",
            "search_results": []
        }
        mock_face_service.index_image.return_value = {"status": "success"}
        mock_get_face.return_value = mock_face_service

        payload = {
            "userId": "user-lost-456",
            "postId": 1001,
            "postType": 0,
            "imageUrl": "https://example.com/lost.jpg"
        }

        with patch('os.path.exists', return_value=True):
            response = self.client.post(self.posts_url, payload, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Post.objects.filter(post_id=1001).exists())

    @patch('app.ai.views._get_face_service')
    @patch('app.ai.views.download_remote_image')
    def test_post_creation_matching_found_post_within_30_days_rejected(self, mock_download, mock_get_face):
        mock_download.return_value = 'fake_image.jpg'
        
        # 1. Create pre-existing Found post in SQLite created 10 days ago
        found_post = Post.objects.create(
            post_id=1002,
            user_id='user-found-123',
            post_type=1,
            image_url='https://example.com/found.jpg',
            is_resolved=False
        )
        Post.objects.filter(post_id=1002).update(created_at=timezone.now() - timedelta(days=10))

        # 2. Mock face search to return high confidence match (85.0% similarity)
        mock_face_service = MagicMock()
        mock_face_service.search_face_by_image.return_value = {
            "status": "success",
            "search_results": [
                {
                    "similarity": 85.0,
                    "metadata": {
                        "postId": 1002,
                        "userId": "user-found-123",
                        "status": "found"
                    }
                }
            ]
        }
        mock_get_face.return_value = mock_face_service

        payload = {
            "userId": "user-lost-456",
            "postId": 1001,
            "postType": 0,
            "imageUrl": "https://example.com/lost.jpg"
        }

        with patch('os.path.exists', return_value=True):
            response = self.client.post(self.posts_url, payload, format='json')

        # Should be rejected with 400 Bad Request
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Post.objects.filter(post_id=1001).exists())
        self.assertIn("A matching found post", response.data["error"])

    @patch('app.ai.views._get_face_service')
    @patch('app.ai.views.download_remote_image')
    def test_post_creation_matching_found_post_older_than_30_days_accepted(self, mock_download, mock_get_face):
        mock_download.return_value = 'fake_image.jpg'
        
        # 1. Create pre-existing Found post in SQLite created 35 days ago
        found_post = Post.objects.create(
            post_id=1002,
            user_id='user-found-123',
            post_type=1,
            image_url='https://example.com/found.jpg',
            is_resolved=False
        )
        Post.objects.filter(post_id=1002).update(created_at=timezone.now() - timedelta(days=35))

        # 2. Mock face search to return high confidence match (85.0% similarity)
        mock_face_service = MagicMock()
        mock_face_service.search_face_by_image.return_value = {
            "status": "success",
            "search_results": [
                {
                    "similarity": 85.0,
                    "metadata": {
                        "postId": 1002,
                        "userId": "user-found-123",
                        "status": "found"
                    }
                }
            ]
        }
        mock_face_service.index_image.return_value = {"status": "success"}
        mock_get_face.return_value = mock_face_service

        payload = {
            "userId": "user-lost-456",
            "postId": 1001,
            "postType": 0,
            "imageUrl": "https://example.com/lost.jpg"
        }

        with patch('os.path.exists', return_value=True):
            response = self.client.post(self.posts_url, payload, format='json')

        # Should be accepted successfully
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Post.objects.filter(post_id=1001).exists())

    @patch('app.ai.views._get_face_service')
    @patch('app.ai.views.download_remote_image')
    def test_post_creation_low_similarity_match_accepted(self, mock_download, mock_get_face):
        mock_download.return_value = 'fake_image.jpg'
        
        # 1. Create pre-existing Found post in SQLite created 10 days ago
        found_post = Post.objects.create(
            post_id=1002,
            user_id='user-found-123',
            post_type=1,
            image_url='https://example.com/found.jpg',
            is_resolved=False
        )
        Post.objects.filter(post_id=1002).update(created_at=timezone.now() - timedelta(days=10))

        # 2. Mock face search to return low confidence match (45.0% similarity)
        mock_face_service = MagicMock()
        mock_face_service.search_face_by_image.return_value = {
            "status": "success",
            "search_results": [
                {
                    "similarity": 45.0,
                    "metadata": {
                        "postId": 1002,
                        "userId": "user-found-123",
                        "status": "found"
                    }
                }
            ]
        }
        mock_face_service.index_image.return_value = {"status": "success"}
        mock_get_face.return_value = mock_face_service

        payload = {
            "userId": "user-lost-456",
            "postId": 1001,
            "postType": 0,
            "imageUrl": "https://example.com/lost.jpg"
        }

        with patch('os.path.exists', return_value=True):
            response = self.client.post(self.posts_url, payload, format='json')

        # Should be accepted successfully because similarity is < 60%
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Post.objects.filter(post_id=1001).exists())

    @patch('app.ai.views._get_face_service')
    @patch('app.ai.views.download_remote_image')
    def test_post_creation_none_metadata_handled_safely(self, mock_download, mock_get_face):
        mock_download.return_value = 'fake_image.jpg'
        
        # Mock face search to return metadata as None (which caused the AttributeError)
        mock_face_service = MagicMock()
        mock_face_service.search_face_by_image.return_value = {
            "status": "success",
            "search_results": [
                {
                    "similarity": 85.0,
                    "metadata": None,
                    "id": "some-face-id"
                }
            ]
        }
        mock_face_service.index_image.return_value = {"status": "success"}
        mock_get_face.return_value = mock_face_service

        payload = {
            "userId": "user-lost-456",
            "postId": 1001,
            "postType": 0,
            "imageUrl": "https://example.com/lost.jpg"
        }

        with patch('os.path.exists', return_value=True):
            response = self.client.post(self.posts_url, payload, format='json')

        # Should handle metadata=None safely and not throw AttributeError (returns 200 OK)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Post.objects.filter(post_id=1001).exists())
