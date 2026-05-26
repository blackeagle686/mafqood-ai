import sys
import os
from unittest.mock import patch, MagicMock

# Mock cv2 and insightface before imports
sys.modules['cv2'] = MagicMock()
sys.modules['insightface'] = MagicMock()
sys.modules['insightface.app'] = MagicMock()

import django
import pytest

# Setup Django first
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mafqood_project.settings')
django.setup()

from django.test import TestCase
from rest_framework.test import APIClient
from app.ai.models import Post, DNAProfile, DNAMatch
from infra.celery.tasks import background_dna_match_task, send_dna_webhook_task


class TestDNAIntegration(TestCase):

    def setUp(self):
        self.client = APIClient()
        # Set authorization header (API Key)
        self.client.credentials(HTTP_X_API_KEY='mafqood-shared-secret-key-2026')
        
        # Create some test posts
        self.post_lost = Post.objects.create(
            post_id=101,
            user_id="user_lost",
            post_type=0, # Lost
            image_url="",
            is_resolved=False
        )
        self.post_found = Post.objects.create(
            post_id=202,
            user_id="user_found",
            post_type=1, # Found
            image_url="",
            is_resolved=False
        )

        # DNA profiles
        self.child_dna = {
            "D3S1358": [15, 16],
            "vWA": [14, 17],
            "TH01": [6, 9.3],
            "FGA": [20, 24]
        }
        self.father_dna = {
            "D3S1358": [16, 18], # shares 16
            "vWA": [17, 18],    # shares 17
            "TH01": [9.3, 10],  # shares 9.3
            "FGA": [20, 22]     # shares 20
        }

    def test_dna_posts_endpoints_unauthorized(self):
        # Remove API key
        self.client.credentials()
        payload = {
            "postId": 101,
            "userId": "user_lost",
            "postType": 0,
            "strData": self.child_dna
        }
        response = self.client.post('/api/ai/dna/posts', payload, format='json')
        assert response.status_code == 401

    @patch('infra.celery.tasks.background_dna_match_task.delay')
    def test_dna_posts_endpoints_happy_path(self, mock_celery_delay):
        payload = {
            "postId": 101,
            "userId": "user_lost",
            "postType": 0,
            "strData": self.child_dna,
            "gender": "XY"
        }
        response = self.client.post('/api/ai/dna/posts', payload, format='json')
        
        assert response.status_code == 202
        assert response.json()["isSuccess"] is True
        
        # Verify DNAProfile is created
        profile = DNAProfile.objects.get(post__post_id=101)
        assert profile.str_data == self.child_dna
        assert profile.gender == "XY"
        
        # Verify background task is triggered
        mock_celery_delay.assert_called_once_with(101)

        # Test DELETE endpoint
        delete_response = self.client.delete('/api/ai/dna/posts', {"postId": 101}, format='json')
        assert delete_response.status_code == 200
        assert not DNAProfile.objects.filter(post__post_id=101).exists()

    def test_dna_posts_endpoints_invalid_data(self):
        payload = {
            "postId": 101,
            "userId": "user_lost",
            "postType": 0,
            "strData": {"TH01": ["invalid", "alleles"]}
        }
        response = self.client.post('/api/ai/dna/posts', payload, format='json')
        assert response.status_code == 400
        assert "Invalid STR data structure" in response.json()["error"]

    def test_dna_search_endpoint(self):
        # Create DNA profile in DB
        DNAProfile.objects.create(
            post=self.post_found,
            str_data=self.father_dna,
            gender="XY"
        )
        
        payload = {
            "strData": self.child_dna,
            "searchType": "parent_child",
            "minOverlap": 3
        }
        response = self.client.post('/api/ai/dna/search/', payload, format='json')
        
        assert response.status_code == 200
        data = response.json()
        assert data["isSuccess"] is True
        assert len(data["results"]) == 1
        assert data["results"][0]["target_id"] == 202
        assert data["results"][0]["score"] == 1.0 # 100% kinship match

    @patch('infra.celery.tasks.send_dna_webhook_task.delay')
    def test_background_dna_match_task(self, mock_webhook_delay):
        # Create Lost DNA Profile (Child)
        DNAProfile.objects.create(
            post=self.post_lost,
            str_data=self.child_dna
        )
        # Create Found DNA Profile (Father)
        DNAProfile.objects.create(
            post=self.post_found,
            str_data=self.father_dna
        )
        
        # Run background task synchronously
        res = background_dna_match_task(101)
        
        assert res["status"] == "completed"
        assert res["matches_found"] == 1
        
        # Verify DNAMatch is stored in DB
        match = DNAMatch.objects.get(missing_post_id=101, found_post_id=202)
        assert match.match_type == "kinship_parent_child"
        assert match.confidence_score == 1.0
        
        # Verify webhook dispatch was triggered
        assert mock_webhook_delay.call_count == 1
        payload = mock_webhook_delay.call_args[0][0]
        assert payload["userId"] == "user_lost"
        assert payload["postId"] == 101
        assert payload["matchedResults"][0]["postId"] == 202
        assert payload["matchedResults"][0]["relationshipType"] == "kinship_parent_child"

    @patch('infra.external.webhook_notifier.WebhookNotifier.send_dna_match_results_to_mafqood')
    def test_send_dna_webhook_task(self, mock_send_webhook):
        mock_send_webhook.return_value = True
        payload = {"test": "payload"}
        
        res = send_dna_webhook_task(payload)
        assert res["status"] == "success"
        mock_send_webhook.assert_called_once_with(payload)
