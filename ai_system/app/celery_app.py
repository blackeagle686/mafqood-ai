from celery import Celery
from .config import config

celery_app = Celery(
    "ai_system",
    broker=config.redis_url,
    backend=config.redis_url, # Adding result backend for task tracking
)

celery_app.autodiscover_tasks(["app.tasks"])
