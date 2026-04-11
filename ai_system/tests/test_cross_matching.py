import pytest
from unittest.mock import MagicMock, patch
import os
import django

# Setup Django before importing models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mafqood_project.settings')
# We need to add 'app' to sys.path so mafqood_project can be found
import sys
sys.path.append(os.path.join(os.getcwd(), 'app'))
django.setup()

from services.face_search_service import FaceSearchService
from app.ai.models import FaceMatch

@pytest.fixture
def face_service():
    with patch('services.face_search_service.FaceCVPipeline'), \
         patch('services.face_search_service.VectorDB'), \
         patch('services.face_search_service.AgeProgressionGAN'), \
         patch('services.face_search_service.WebhookNotifier') as mock_webhook:
        service = FaceSearchService()
        service.mock_webhook = mock_webhook
        yield service
        # Manual cleanup because mark.django_db is not working without pytest-django
        FaceMatch.objects.all().delete()

class TestCrossMatching:
    
    def test_compute_match_score(self, face_service):
        # Perfect match
        score = face_service.compute_match_score(1.0, 0.0, 1.0)
        assert score == pytest.approx(1.0)
        
        # 0.5 face similarity, 0 days, 0 loc
        # 0.7*0.5 + 0.2*1.0 + 0.1*0.0 = 0.35 + 0.2 = 0.55
        score = face_service.compute_match_score(0.5, 0.0, 0.0)
        assert score == pytest.approx(0.55)

    def test_match_on_insert_new_match(self, face_service):
        # Mock VectorDB search (returns all, including same-status)
        face_service.vdb.search.return_value = {
            "ids": [["face_found_1", "face_missing_2"]],
            "distances": [[0.1, 0.05]], 
            "metadatas": [
                [
                    {"postId": 200, "status": "found", "location": "Cairo"},
                    {"postId": 101, "status": "missing"} # Self/Duplicate
                ]
            ]
        }
        
        embedding = [0.1] * 512
        metadata = {"postId": 100, "status": "missing", "location": "Cairo"}
        
        face_service.match_on_insert(embedding, "missing", metadata)
        
        # Verify cross-match (Missing 100 <-> Found 200) saved
        assert FaceMatch.objects.filter(missing_post_id=100, found_post_id=200).exists()
        # Verify SAME-status match (Missing 100 <-> Missing 101) was NOT saved as an alert match
        assert not FaceMatch.objects.filter(missing_post_id=100, found_post_id=101).exists()
        # Verify webhook called for the cross-match
        assert face_service.mock_webhook.send_high_confidence_match_alert.called

    def test_match_on_insert_deduplication(self, face_service):
        # Pre-create match
        FaceMatch.objects.create(
            missing_post_id=100,
            found_post_id=200,
            combined_score=0.9,
            face_similarity=0.9,
            time_score=1.0,
            location_score=1.0
        )
        
        # Mock VectorDB search
        face_service.vdb.search.return_value = {
            "ids": [["face_found_1"]],
            "distances": [[0.1]],
            "metadatas": [[{"postId": 200, "status": "found"}]]
        }
        
        embedding = [0.1] * 512
        metadata = {"postId": 100, "status": "missing"}
        
        # Reset mock before call
        face_service.mock_webhook.send_high_confidence_match_alert.reset_mock()
        
        # Call again
        face_service.match_on_insert(embedding, "missing", metadata)
        
        # Webhook should NOT be called again (deduplication)
        assert not face_service.mock_webhook.send_high_confidence_match_alert.called

if __name__ == "__main__":
    pytest.main([__file__])
