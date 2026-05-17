import sys
import os
import django
import pytest
from unittest.mock import patch, MagicMock

# Setup Django settings before importing modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mafqood_project.settings')
os.environ.setdefault('INSIGHTFACE_OFFLINE', '1')
django.setup()

from django.test import TestCase
from rest_framework.test import APIClient
from app.ai.models import Post

class TestDotNetIntegrationFlow(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.posts_url = '/api/ai/posts'
        self.resolve_url = '/api/ai/posts/mark-resolved'
        self.api_key = 'mafqood-shared-secret-key-2026'

    # --- 1. Authentication Tests ---
    def test_authentication_missing_key(self):
        response = self.client.post(self.posts_url, {}, format='json')
        self.assertEqual(response.status_code, 401)

    def test_authentication_invalid_key(self):
        self.client.credentials(HTTP_X_API_KEY='invalid-key')
        response = self.client.post(self.posts_url, {}, format='json')
        self.assertEqual(response.status_code, 401)

    # --- 2. Post Lifecycle Tests (POST / Create & Match) ---
    @patch('app.ai.views._get_face_service')
    @patch('app.ai.views.download_remote_image')
    @patch('infra.celery.tasks.send_webhook_task.delay')
    def test_post_creation_lost_and_found_matching(self, mock_webhook_delay, mock_download, mock_get_face):
        # Mock download to return a fake local file
        mock_download.return_value = 'fake_image.jpg'
        
        # Mock face service
        mock_face_service = MagicMock()
        mock_face_service.index_image.return_value = {"status": "success"}
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

        # Configure API key
        self.client.credentials(HTTP_X_API_KEY=self.api_key)

        # First, register the opposite post in SQLite (Found post)
        opposite_post = Post.objects.create(
            post_id=1002,
            user_id='user-found-123',
            post_type=1,
            image_url='https://example.com/found.jpg',
            is_resolved=False
        )

        # Create the Lost post (postType = 0)
        payload = {
            "userId": "user-lost-456",
            "postId": 1001,
            "postType": 0,
            "imageUrl": "https://example.com/lost.jpg"
        }

        with patch('os.path.exists', return_value=True):
            response = self.client.post(self.posts_url, payload, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["isSuccess"], True)

        # Verify SQLite post creation
        post = Post.objects.get(post_id=1001)
        self.assertEqual(post.user_id, "user-lost-456")
        self.assertEqual(post.post_type, 0)
        self.assertFalse(post.is_resolved)

        # Verify indexing calls
        mock_face_service.index_image.assert_called_once()
        mock_face_service.search_face_by_image.assert_called_once()

        # Verify webhook dispatch: 1 match with 85% mapped to 0.85
        mock_webhook_delay.assert_called_once_with({
            "userId": "user-lost-456",
            "postId": 1001,
            "matchedResults": [
                {
                    "userId": "user-found-123",
                    "postId": 1002,
                    "confidenceScore": 0.85
                }
            ]
        })

    # --- 3. Post Update Test (PUT) ---
    @patch('app.ai.views.VectorDB')
    @patch('app.ai.views._get_face_service')
    @patch('app.ai.views.download_remote_image')
    def test_post_update_clears_old_index(self, mock_download, mock_get_face, mock_vector_db_cls):
        mock_download.return_value = 'fake_image.jpg'
        mock_face_service = MagicMock()
        mock_face_service.index_image.return_value = {"status": "success"}
        mock_face_service.search_face_by_image.return_value = {"status": "success", "search_results": []}
        mock_get_face.return_value = mock_face_service

        mock_vdb = MagicMock()
        mock_vdb.get_vectors.return_value = {"ids": ["old_face_1"]}
        mock_vector_db_cls.return_value = mock_vdb

        # Create existing post in SQLite
        post = Post.objects.create(
            post_id=1001,
            user_id='user-lost-456',
            post_type=0,
            image_url='https://example.com/old.jpg',
            is_resolved=False
        )

        self.client.credentials(HTTP_X_API_KEY=self.api_key)
        payload = {
            "userId": "user-lost-456",
            "postId": 1001,
            "postType": 0,
            "imageUrl": "https://example.com/new.jpg"
        }

        with patch('os.path.exists', return_value=True):
            response = self.client.put(self.posts_url, payload, format='json')

        self.assertEqual(response.status_code, 200)

        # Verify old vectors query and delete were triggered
        mock_vdb.get_vectors.assert_called_once_with(where={"postId": 1001})
        mock_vdb.delete.assert_called_once_with(ids=["old_face_1"])

        # Verify SQLite is updated
        post.refresh_from_db()
        self.assertEqual(post.image_url, 'https://example.com/new.jpg')

    # --- 4. Post Delete Test (DELETE) ---
    @patch('app.ai.views.VectorDB')
    def test_post_deletion_cleans_db_and_index(self, mock_vector_db_cls):
        mock_vdb = MagicMock()
        mock_vdb.get_vectors.return_value = {"ids": ["face_to_delete"]}
        mock_vector_db_cls.return_value = mock_vdb

        # Create existing post in SQLite
        post = Post.objects.create(
            post_id=1001,
            user_id='user-lost-456',
            post_type=0,
            image_url='https://example.com/lost.jpg',
            is_resolved=False
        )

        self.client.credentials(HTTP_X_API_KEY=self.api_key)
        payload = {
            "userId": "user-lost-456",
            "postId": 1001,
            "postType": 0,
            "imageUrl": "https://example.com/lost.jpg"
        }

        response = self.client.delete(self.posts_url, payload, format='json')
        self.assertEqual(response.status_code, 200)

        # Verify vectors deleted
        mock_vdb.get_vectors.assert_called_once_with(where={"postId": 1001})
        mock_vdb.delete.assert_called_once_with(ids=["face_to_delete"])

        # Verify post removed from SQLite
        self.assertFalse(Post.objects.filter(post_id=1001).exists())

    # --- 5. Mark Resolved Test (POST /mark-resolved) ---
    @patch('app.ai.views.VectorDB')
    def test_mark_resolved_flags_sqlite_and_clears_vectors(self, mock_vector_db_cls):
        mock_vdb = MagicMock()
        mock_vdb.get_vectors.return_value = {"ids": ["face_resolved"]}
        mock_vector_db_cls.return_value = mock_vdb

        post = Post.objects.create(
            post_id=1001,
            user_id='user-lost-456',
            post_type=0,
            image_url='https://example.com/lost.jpg',
            is_resolved=False
        )

        self.client.credentials(HTTP_X_API_KEY=self.api_key)
        payload = {
            "userId": "user-lost-456",
            "postId": 1001
        }

        response = self.client.post(self.resolve_url, payload, format='json')
        self.assertEqual(response.status_code, 200)

        # Verify SQLite post state updated to is_resolved=True
        post.refresh_from_db()
        self.assertTrue(post.is_resolved)

        # Verify vectors deleted
        mock_vdb.get_vectors.assert_called_once_with(where={"postId": 1001})
        mock_vdb.delete.assert_called_once_with(ids=["face_resolved"])

    def test_mark_resolved_non_existent_post(self):
        self.client.credentials(HTTP_X_API_KEY=self.api_key)
        payload = {
            "userId": "user-lost-456",
            "postId": 9999
        }
        response = self.client.post(self.resolve_url, payload, format='json')
        self.assertEqual(response.status_code, 404)

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
