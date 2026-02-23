import sys
import os
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.celery_app import celery_app

# Configure Celery for testing
celery_app.conf.update(
    task_always_eager=True,
    task_eager_propagates=True,
    broker_url="memory://",
    result_backend="rpc://"
)

client = TestClient(app)

def test_classify_sync_good():
    response = client.post("/api/classify?text=انا احب التفاح")
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "انا احب التفاح"
    assert data["label"] == "good"

def test_classify_sync_bad():
    response = client.post("/api/classify?text=انت حمار وقح")
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == "bad"

def test_classify_empty():
    response = client.post("/api/classify?text=")
    assert response.status_code == 400
    assert response.json()["detail"] == "Text is required"

def test_classify_async():
    # Mock celery task at the endpoint level
    with patch("app.api.endpoints.classify.process_text_task") as mock_task:
        mock_mock_task = MagicMock()
        mock_mock_task.id = "test-task-id"
        mock_task.delay.return_value = mock_mock_task
        
        response = client.post("/api/classify?text=test text&async_mode=True")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "test-task-id"
        assert data["status"] == "processing"

@patch("app.celery_app.celery_app.AsyncResult")
def test_get_status(mock_async_result):
    # Mock task result
    mock_result = MagicMock()
    mock_result.status = "SUCCESS"
    mock_result.ready.return_value = True
    mock_result.result = {"text": "test", "label": "good"}
    mock_async_result.return_value = mock_result
    
    response = client.get("/api/classify/status/test-task-id")
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == "test-task-id"
    assert data["status"] == "SUCCESS"
    assert data["result"]["label"] == "good"

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
