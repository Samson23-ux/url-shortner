api: uvicorn app.main:app --port 8000
worker: celery -A app.task.celery_app worker -P gevent -l info
beat: celery -A app.task.celery_app beat -l info
flower: celery -A app.task.celery_app flower --port=5555