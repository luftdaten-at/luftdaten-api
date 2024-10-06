from celery import Celery
from celery.schedules import crontab

celery_worker = Celery(
    "worker",
    broker="amqp://user:password@rabbitmq:5672/",
    backend="rpc://"
)

# Tasks automatisch entdecken
#celery_worker.autodiscover_tasks(['tasks'])
celery_worker.conf.imports = ('tasks.periodic_tasks',)

# Task-Routing konfigurieren
celery_worker.conf.update(
    task_routes={
        "tasks.periodic_tasks.import_sensor_community_data": {"queue": "sensor_data_queue"},
    }
)

# Beat-Scheduler für regelmäßige Tasks
celery_worker.conf.beat_schedule = {
    'import_sensor_community_data_every_5_minutes': {
        'task': 'tasks.periodic_tasks.import_sensor_community_data',
        'schedule': crontab(minute='*/5'),  # Alle 5 Minuten
    },
}

if __name__ == "__main__":
    celery_worker.start()