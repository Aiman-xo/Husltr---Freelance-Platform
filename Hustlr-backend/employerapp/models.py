from django.db import models
from authapp.models import Profile,HustlrUsers
from workerapp.models import WorkerProfile

from cloudinary_storage.storage import MediaCloudinaryStorage

# Create your models here.

class EmployerProfile(models.Model):
    user = models.OneToOneField(Profile,on_delete=models.CASCADE,related_name='employer_profile')
    company_name = models.CharField(max_length=100)

    def __str__(self):
        return self.company_name
    
class JobRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    )

    employer = models.ForeignKey(EmployerProfile, on_delete=models.CASCADE, related_name='sent_hiring_requests')
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name='received_job_offers')
    
    description = models.TextField()
    city = models.CharField(max_length=255)
    project_image = models.ImageField(
        upload_to='job_requests/', 
        storage=MediaCloudinaryStorage(), # Explicitly set Cloudinary here
        null=True, 
        blank=True
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __clash_prevention__(self):
        # Prevent employer from requesting themselves
        pass

    def __str__(self):
        return self.description
    

class Notification(models.Model):
    # The person receiving the notification
    recipient = models.ForeignKey(HustlrUsers, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # To link back to the job request if they click it
    related_id = models.IntegerField(null=True, blank=True) 
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']