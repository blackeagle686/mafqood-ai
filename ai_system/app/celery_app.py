import os
import sys
from pathlib import Path

# Add the parent directory to sys.path to allow imports from 'app.'
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from celery import Celery

# Set default Django settings module for 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mafqood_project.settings')

celery_app = Celery("ai_system")

# Load configuration from Django settings, including CELERY_* settings.
celery_app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
celery_app.autodiscover_tasks()

# Standard Celery optimized settings (now pulled from settings if defined)
# but we can keep some here if preferred
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)

# Celery Beat Schedule
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'evaluate-clustering-every-15-mins': {
        'task': 'infra.celery.tasks.evaluate_and_trigger_clustering',
        'schedule': crontab(minute='*/15'),
    },
    'poll-facebook-groups-every-15-mins': {
        'task': 'infra.celery.tasks.poll_facebook_groups_task',
        'schedule': crontab(minute='*/15'),
    },
}
