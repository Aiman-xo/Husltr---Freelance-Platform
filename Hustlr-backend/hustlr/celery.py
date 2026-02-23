import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hustlr.settings")

app = Celery("hustlr")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
