from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "datanexus",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.services.tasks.process_file_task": {"queue": "file_processing"},
        "app.services.tasks.sync_onedrive_task": {"queue": "onedrive_sync"},
        "app.services.tasks.generate_report_task": {"queue": "reports"},
        "app.services.tasks.generate_embeddings_task": {"queue": "embeddings"},
    },
    task_default_queue="default",
    task_default_retry_delay=60,
    task_max_retries=3,
)

celery_app.autodiscover_tasks(["app.services"])
