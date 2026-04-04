"""
Tests for the AI (LLM) service endpoints:
  - POST /api/ai/moderate/
  - POST /api/ai/extract/

All LLM calls are mocked so tests run without network access or an API key.
"""
import sys
import os
import django
import pytest

# ── Setup Django settings before importing DRF ─────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mafqood_project.settings')
os.environ.setdefault('INSIGHTFACE_OFFLINE', '1')  # Skip model download
django.setup()

from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient


# ═══════════════════════════════════════════════════════════════════════════
#  Moderation endpoint — /api/ai/moderate/
# ═══════════════════════════════════════════════════════════════════════════

class TestModerateTextEndpoint(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/ai/moderate/'

    # ── Happy path ──────────────────────────────────────────────────────────

    @patch('app.ai.views._get_llm_service')
    def test_moderate_good_text(self, mock_get):
        mock_llm = MagicMock()
        mock_llm.classify_text_appropriateness.return_value = 'good'
        mock_get.return_value = mock_llm

        response = self.client.post(self.url, {'text': 'انا احب التفاح'}, format='json')

        assert response.status_code == 200
        assert response.data['label'] == 'good'
        assert response.data['source'] == 'llm'
        assert response.data['text'] == 'انا احب التفاح'

    @patch('app.ai.views._get_llm_service')
    def test_moderate_bad_text(self, mock_get):
        mock_llm = MagicMock()
        mock_llm.classify_text_appropriateness.return_value = 'bad'
        mock_get.return_value = mock_llm

        response = self.client.post(self.url, {'text': 'انت حمار وقح'}, format='json')

        assert response.status_code == 200
        assert response.data['label'] == 'bad'
        assert response.data['source'] == 'llm'

    @patch('app.ai.views._get_llm_service')
    def test_moderate_llm_ambiguous_defaults_to_good(self, mock_get):
        """If LLM returns 'unknown', endpoint should default to 'good' with source=unavailable."""
        mock_llm = MagicMock()
        mock_llm.classify_text_appropriateness.return_value = 'unknown'
        mock_get.return_value = mock_llm

        response = self.client.post(self.url, {'text': 'some ambiguous text'}, format='json')

        assert response.status_code == 200
        assert response.data['label'] == 'good'
        assert response.data['source'] == 'unavailable'

    # ── Error cases ─────────────────────────────────────────────────────────

    def test_moderate_missing_text_returns_400(self):
        response = self.client.post(self.url, {}, format='json')
        assert response.status_code == 400

    def test_moderate_blank_text_returns_400(self):
        response = self.client.post(self.url, {'text': '   '}, format='json')
        assert response.status_code == 400

    @patch('app.ai.views._get_llm_service')
    def test_moderate_llm_exception_returns_503(self, mock_get):
        mock_llm = MagicMock()
        mock_llm.classify_text_appropriateness.side_effect = RuntimeError('API timeout')
        mock_get.return_value = mock_llm

        response = self.client.post(self.url, {'text': 'Hello'}, format='json')

        assert response.status_code == 503
        assert 'error' in response.data


# ═══════════════════════════════════════════════════════════════════════════
#  Entity extraction endpoint — /api/ai/extract/
# ═══════════════════════════════════════════════════════════════════════════

class TestExtractEntitiesEndpoint(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/ai/extract/'
        self.sample_entities = {
            'status': 'missing',
            'location': 'Cairo',
            'age_estimation': 8,
            'clothing': 'blue shirt',
        }

    # ── Happy path ──────────────────────────────────────────────────────────

    @patch('app.ai.views._get_llm_service')
    def test_extract_text_only(self, mock_get):
        mock_llm = MagicMock()
        mock_llm.extract_entities_from_post.return_value = self.sample_entities
        mock_get.return_value = mock_llm

        payload = {'text': 'طفل مفقود في القاهرة عمره 8 سنوات'}
        response = self.client.post(self.url, payload, format='json')

        assert response.status_code == 200
        assert response.data['status'] == 'missing'
        assert response.data['location'] == 'Cairo'
        assert response.data['age_estimation'] == 8
        assert response.data['clothing'] == 'blue shirt'
        assert response.data['image_used'] is False
        assert response.data['input_text'] == payload['text']

        # Verify LLM was called without an image
        mock_llm.extract_entities_from_post.assert_called_once_with(
            payload['text'], image_url=None
        )

    @patch('app.ai.views._get_llm_service')
    def test_extract_with_image_url(self, mock_get):
        mock_llm = MagicMock()
        mock_llm.extract_entities_from_post.return_value = self.sample_entities
        mock_get.return_value = mock_llm

        payload = {
            'text': 'تم العثور على طفل في الاسكندرية',
            'image_url': 'https://example.com/photo.jpg',
        }
        response = self.client.post(self.url, payload, format='json')

        assert response.status_code == 200
        assert response.data['image_used'] is True
        mock_llm.extract_entities_from_post.assert_called_once_with(
            payload['text'], image_url=payload['image_url']
        )

    # ── Error cases ─────────────────────────────────────────────────────────

    def test_extract_missing_text_returns_400(self):
        response = self.client.post(self.url, {}, format='json')
        assert response.status_code == 400

    def test_extract_invalid_image_url_returns_400(self):
        response = self.client.post(
            self.url, {'text': 'some text', 'image_url': 'not-a-url'}, format='json'
        )
        assert response.status_code == 400

    @patch('app.ai.views._get_llm_service')
    def test_extract_llm_exception_returns_503(self, mock_get):
        mock_llm = MagicMock()
        mock_llm.extract_entities_from_post.side_effect = RuntimeError('Network error')
        mock_get.return_value = mock_llm

        response = self.client.post(self.url, {'text': 'some text'}, format='json')

        assert response.status_code == 503
        assert 'error' in response.data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
