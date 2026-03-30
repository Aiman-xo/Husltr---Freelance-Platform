from django.contrib import admin
from .models import EmployerProfile,JobRequest,Skill

# Register your models here.
admin.site.register(EmployerProfile)
admin.site.register(JobRequest)
admin.site.register(Skill)