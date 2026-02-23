from django.db import models
from authapp.models import Profile

# Create your models here.
class Location(models.Model):
    user = models.OneToOneField(Profile,on_delete=models.CASCADE)
    latitude = models.FloatField()
    longitude = models.FloatField()

    address = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    
    