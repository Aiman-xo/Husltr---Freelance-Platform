from django.db import models
from authapp.models import Profile
# Create your models here.


class Skill(models.Model):
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name
    

class WorkerProfile(models.Model):
    user = models.OneToOneField(Profile,on_delete=models.CASCADE,related_name='worker_profile')
    base_Pay = models.IntegerField()
    job_description = models.TextField()
    experience = models.IntegerField()
    hourly_rate = models.IntegerField()
    
    skills = models.ManyToManyField(Skill,related_name='worker_skills')

    def __str__(self):
        return self.user.username
