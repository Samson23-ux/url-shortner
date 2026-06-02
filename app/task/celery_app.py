from celery import Celery


from app.core.config import get_settings


celery_app = Celery(main="celery_app", broker=get_settings().API_BROKER)


celery_app.config_from_object("app.tasks.celeryconfig")
celery_app.autodiscover_tasks(["app.task.celery_task"])
