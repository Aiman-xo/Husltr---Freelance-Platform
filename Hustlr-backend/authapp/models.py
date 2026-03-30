import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from .managers import CustomManager


# Create your models here.
class HustlrUsers(AbstractUser):
    email = models.EmailField(unique=True)
    username = None
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = CustomManager()


class Profile(models.Model):

    ROLE_CHOICES = (
        ("worker", "Worker"),
        ("employer", "Employer"),
    )

    user = models.OneToOneField(
        HustlrUsers, on_delete=models.CASCADE, related_name="profile"
    )
    image = models.ImageField(upload_to="profile_pics")
    username = models.CharField(max_length=100)
    active_role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default="worker"
    )
    city = models.CharField(max_length=100)
    fcm_token = models.TextField(null=True, blank=True)
    phone_number = models.CharField(max_length=10)

    def __str__(self):
        return self.username


class ResetPassword(models.Model):
    user = models.OneToOneField(HustlrUsers, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    reset_session = models.UUIDField(default=uuid.uuid4, unique=True)
    is_verified = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=5)
