import pytest
from aerosynthx.task_queue import celery_app

@pytest.fixture(autouse=True)
def celery_eager_mode():
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
