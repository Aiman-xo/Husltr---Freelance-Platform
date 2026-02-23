from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ResetPassword
from .tasks import send_otp_email

@receiver(post_save,sender = ResetPassword)
def send_otp_signal(sender,instance,created,**kwargs):
    otp = instance.otp
    email = instance.user.email

    send_otp_email.delay(email,otp)

