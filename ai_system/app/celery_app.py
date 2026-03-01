from celery import Celery
import os

# Get Redis URL with fallback - don't import config at module level
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "ai_system",
    broker=redis_url,
    backend=redis_url,
)

# Configure Celery with connection pooling and optimized settings
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Connection pooling to reduce CPU and connection issues
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_pool_limit=10,
    
    # Redis Backend configuration
    redis_socket_keepalive=True,
    redis_socket_keepalive_options={'TCP_KEEPIDLE': 60},
    
    # Worker configuration
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    worker_disable_rate_limits=True,
    
    # Task timeout configuration - INCREASED for heavy CV processing
    task_time_limit=7200,  # 2 hours for heavy face recognition
    task_soft_time_limit=6900,  # 1h55m soft limit
    task_acks_late=True,  # Acknowledge task only after successful completion
    task_reject_on_worker_lost=True,
    
    # Result backend configuration
    result_expires=3600,
    result_compression=True,
    result_backend_transport_options={
        'master_name': 'mymaster',
        'retry_on_timeout': True,
        'connection_retry_on_timeout': True,
        'socket_connect_timeout': 5,
        'socket_timeout': 5,
        'connection_pool_class_kwargs': {'max_connections': 50}
    },
)

celery_app.autodiscover_tasks(["app.tasks"])

# Celery Beat Schedule
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'evaluate-clustering-every-15-mins': {
        'task': 'app.tasks.cluster_tasks.evaluate_and_trigger_clustering',
        'schedule': crontab(minute='*/15'),
    },
}
