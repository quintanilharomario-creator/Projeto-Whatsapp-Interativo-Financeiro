from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "saas_financeiro",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.tasks.ai_tasks",
        "app.workers.tasks.whatsapp_tasks",
        "app.workers.tasks.audio_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "ai.*": {"queue": "ai"},
        "whatsapp.*": {"queue": "whatsapp"},
        "audio.*": {"queue": "audio"},
    },
)
