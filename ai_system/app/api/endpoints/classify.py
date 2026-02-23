from fastapi import APIRouter, HTTPException
from app.tasks.nlp_tasks import process_text_task
from app.core.nlp_pipeline import classify_text
from typing import Optional
from app.celery_app import celery_app

router = APIRouter()

@router.post('/classify')
async def classify(text: str, async_mode: bool = False):
    """
    Classify text for bad words.
    - async_mode=True: Returns a task ID for background processing.
    - async_mode=False (default): Returns immediate classification result.
    """
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    if async_mode:
        task = process_text_task.delay(text)
        return {"task_id": task.id, "status": "processing"}
    
    # Synchronous classification
    label = classify_text(text)
    return {
        "text": text,
        "label": label
    }

@router.get('/classify/status/{task_id}')
async def get_status(task_id: str):
    """
    Check the status of an asynchronous classification task.
    """
    task_result = celery_app.AsyncResult(task_id)
    
    result = {
        "task_id": task_id,
        "status": task_result.status,
        "result": task_result.result if task_result.ready() else None
    }
    return result
