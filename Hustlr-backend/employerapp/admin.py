from django.contrib import admin
from .models import EmployerProfile,JobRequest

# Register your models here.
admin.site.register(EmployerProfile)
admin.site.register(JobRequest)