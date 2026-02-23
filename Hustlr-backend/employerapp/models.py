from django.db import models
from authapp.models import Profile

# Create your models here.

class EmployerProfile(models.Model):
    user = models.OneToOneField(Profile,on_delete=models.CASCADE,related_name='employer_profile')
    company_name = models.CharField(max_length=100)
    
    