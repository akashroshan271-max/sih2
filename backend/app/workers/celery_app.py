"""Celery application for SLA sweeps and asynchronous document extraction.

    celery -A app.workers.celery_app.celery worker --loglevel=info
    celery -A app.workers.celery_app.celery beat --loglevel=info
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery = Celery(
    "veriflow",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=270,
    worker_max_tasks_per_child=200,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        # Rule 3: dwell time is monotonic, but hourly sweeps keep the trail
        # close to the breach instead of waiting for a nightly batch.
        "sla-dwell-sweep": {
            "task": "sla.sweep",
            "schedule": crontab(minute=0),
        },
    },
)
