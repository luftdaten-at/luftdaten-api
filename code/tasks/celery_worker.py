from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "worker",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0"
)

celery_app.conf.update(
    task_routes={
        "tasks.periodic_tasks.import_sensor_data": {"queue": "sensor_data_queue"},
    }
)

celery_app.conf.beat_schedule = {
    'import_sensor_community_data_every_5_minutes': {
        'task': 'tasks.periodic_tasks.import_sensor_community_data',
        'schedule': crontab(minute='*/5'),  # Alle 5 Minuten
    },
}