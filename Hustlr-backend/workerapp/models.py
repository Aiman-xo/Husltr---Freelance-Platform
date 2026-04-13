from django.db import models
from authapp.models import Profile
from django.core.validators import MaxValueValidator, MinValueValidator
# Create your models here.


class Skill(models.Model):
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name
    

class WorkerProfile(models.Model):
    user = models.OneToOneField(Profile,on_delete=models.CASCADE,related_name='worker_profile')
    base_Pay = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(99999)])
    job_description = models.TextField()
    experience = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(999)])
    hourly_rate = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(9999)])
    
    skills = models.ManyToManyField(Skill,related_name='worker_skills')

    def __str__(self):
        return self.user.username
