from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')

# Load task modules from all registered Django app configs.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Configure the schedule
app.conf.beat_schedule = {
    'distribute-pool-earnings': {
        'task': 'market.tasks.distribute_pool_task',
        # Run at 12:20 AM every day
        'schedule': crontab(hour=0, minute=20),
    },
}

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()
