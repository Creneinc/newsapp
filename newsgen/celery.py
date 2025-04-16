# newsgen/celery.py
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'newsgen.settings')

app = Celery('newsgen')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

CELERY_BEAT_SCHEDULE = {
    'calculate-daily-earnings': {
        'task': 'articles.tasks.calculate_earnings',
        'schedule': crontab(hour=0, minute=0),  # Run daily at midnight
    },
    'process-monthly-payouts': {
        'task': 'articles.tasks.process_payouts',
        'schedule': crontab(0, 0, day_of_month='1'),  # Run on the 1st of each month
    },
}
