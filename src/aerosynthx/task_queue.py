"""Celery application configuration."""

from celery import Celery

# For local development, assume Redis is running on the default port.
# In a production environment, this would be configured via environment variables.
BROKER_URL = "redis://localhost:6379/0"
RESULT_BACKEND = "redis://localhost:6379/0"

celery_app = Celery(
    "aerosynthx",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["aerosynthx.workflow.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
)
