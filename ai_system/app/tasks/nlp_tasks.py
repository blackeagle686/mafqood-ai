from celery import shared_task
from app.core.nlp_pipeline import classify_text

@shared_task(name="app.tasks.nlp_tasks.process_text_task")
def process_text_task(text: str):
    """
    Process text to classify if it contains bad words.
    """
    label = classify_text(text)
    return {
        "text": text,
        "label": label,
        "status": "completed"
    }
