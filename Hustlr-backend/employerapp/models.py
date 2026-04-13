from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from authapp.models import Profile,HustlrUsers
from workerapp.models import WorkerProfile
from workerapp.models import Skill
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
        ('starting', 'Starting'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    )

    employer = models.ForeignKey(EmployerProfile, on_delete=models.CASCADE, related_name='sent_hiring_requests')
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name='received_job_offers')

    # used to identify the worker job interesets on a job post.
    job_post = models.ForeignKey('JobPost', on_delete=models.SET_NULL, null=True, blank=True, related_name='applications')
    
    description = models.TextField()
    city = models.CharField(max_length=255)
    project_image = models.ImageField(
        upload_to='job_requests/', 
        null=True, 
        blank=True
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    contract_hourly_rate = models.IntegerField(null=True, blank=True)
    estimated_hours = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0.01), MaxValueValidator(9999)])
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_timer_active = models.BooleanField(default=False)

    expiry_notification_sent = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes =[
            models.Index(fields=['created_at','status'])
        ]

    def __clash_prevention__(self):
        # Prevent employer from requesting themselves
        pass

    def __str__(self):
        return self.description

class JobPost(models.Model):
    employer = models.ForeignKey(EmployerProfile, on_delete=models.CASCADE, related_name='sent_hiring_posts')
    title = models.CharField(max_length=100)
    description = models.TextField()
    city = models.CharField(max_length=100)
    required_skills = models.ManyToManyField(Skill, related_name='job_posts',blank=True)  
    job_image = models.ImageField(upload_to='job_posts/',null=True,blank=True)

class JobMaterials(models.Model):
    job = models.ForeignKey(JobRequest, on_delete=models.CASCADE, related_name='materials')
    item_description = models.CharField(max_length=255)
    # The Employer "Tick" field
    is_available_at_site = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.item_description} for Job #{self.job.id}"
    

class JobBilling(models.Model):
    job = models.OneToOneField(JobRequest, on_delete=models.CASCADE, related_name='billing_info')
    
    # Section 1: Work Pay (Automatically calculated from time * rate)
    labor_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    material_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0), MaxValueValidator(99999)])
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    was_penalty_applied = models.BooleanField(default=False)
    bill_image = models.ImageField(upload_to='job_bills/', null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    # --- NEW FIELDS FOR RAZORPAY ---

    razorpay_order_id = models.CharField(max_length=100, null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Billing for Job #{self.job.id} - Total: {self.total_amount}"
    

class Notification(models.Model):
    # The person receiving the notification
    recipient = models.ForeignKey(HustlrUsers, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # To link back to the job request if they click it
    related_id = models.IntegerField(null=True, blank=True) 
    
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        # Compound index for the exact query in your View
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
        ]
