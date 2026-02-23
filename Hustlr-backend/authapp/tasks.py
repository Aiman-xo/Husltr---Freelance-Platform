from django.core.mail import send_mail,send_mass_mail
from django.conf import settings
from celery import shared_task
from .models import HustlrUsers
from django.utils import timezone
from datetime import timedelta

@shared_task(bind = True,autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
def send_otp_email(self,email,otp):
    subject = 'Password Reset OTP'
    message = (
        f'Hello {email}\n\n'
        f'OTP : {otp}'
        
    )

    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [email],
        fail_silently=True
    )

@shared_task
def send_come_back_email():
    three_days_ago = timezone.now() - timedelta(days=3)
    inactive_users = HustlrUsers.objects.filter(last_login__lte=three_days_ago)
    
    # We prepare a list of tuples for send_mass_mail
    # Format: (subject, message, from_email, recipient_list)
    email_data = []
    
    for user in inactive_users:
        print(user.email)
        subject = 'Time to come back, Warrior!'
        # Personalize the message inside the loop
        message = (
            f'It has been too long, warrior {user.email}\n\n'
            f'Return to your throne 👑'
        )
        email_data.append((
            subject, 
            message, 
            settings.EMAIL_HOST_USER, 
            [user.email]
        ))

    # send_mass_mail opens 1 connection for ALL emails
    if email_data:
        send_mass_mail(tuple(email_data), fail_silently=True)
        
    return f"Sent {len(email_data)} emails."