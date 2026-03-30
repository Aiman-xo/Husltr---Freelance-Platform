from django.db import transaction
from django.db.models.signals import post_save,m2m_changed
from django.dispatch import receiver
from .models import JobPost
from .tasks import send_job_to_n8n

@receiver(m2m_changed,sender=JobPost.required_skills.through)
def trigger_job_post(sender,instance,action,**kwargs):
    if action == 'post_add':
            
        skills_list = list(instance.required_skills.values_list('name', flat=True))
        if not skills_list: 
            skills_list = ['General']
        
        try:
            # Chain: JobPost -> EmployerProfile -> Profile -> Location
            location = instance.employer.user.location 
            lat = location.latitude
            lng = location.longitude
            
            print('DEBUG--------',lat,lng,'-------------')
        except Exception:
            # If any part of the chain is missing, we use 0.0
            # or you can choose not to send the task at all
            lat, lng = 0.0, 0.0

        payload={
            'job_id':instance.id,
            'employer_id':instance.employer.id,
            'title':instance.title,
            'required_skills': skills_list,
            'lat':float(lat),
            'lng':float(lng),
            'city':instance.city,
            'job_image':instance.job_image.url if instance.job_image else None
        }
    
        send_job_to_n8n.delay(payload)
        