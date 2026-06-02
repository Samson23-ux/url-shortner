from celery.schedules import crontab


from app.task.celery_app import celery_app


celery_app.conf.beat_schedule = {
    "send_reminder": {
        "task": "app.task.celery_task.send_reminder_email",
        "schedule": crontab(minute="0", hour="*/2")
    },

    "flush_clicks": {
        "task": "app.task.celery_task.flush_clicks",
        "schedule": crontab(minute="*/3")
    },

    "delete_users": {
        "task": "app.task.celery_task.delete_deactivated_users",
        "schedule": crontab(minute="0", hour="0", day_of_month="20")
    }
}
