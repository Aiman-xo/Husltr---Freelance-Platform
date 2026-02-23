from django.contrib import admin
from .models import HustlrUsers,Profile
from workerapp.models import WorkerProfile

# Register your models here.
admin.site.register(HustlrUsers)
admin.site.register(Profile)
admin.site.register(WorkerProfile)
