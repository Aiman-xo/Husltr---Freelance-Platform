from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ResetPassword,Profile
from .tasks import send_otp_email
from .publisher import publish_user_details

@receiver(post_save,sender = ResetPassword)
def send_otp_signal(sender,instance,created,**kwargs):
    otp = instance.otp
    email = instance.user.email

    send_otp_email.delay(email,otp)

@receiver(post_save,sender=Profile)
def trigger_user_data(sender,instance,created,**kwargs):
    role = instance.active_role
    user_id = instance.user.id
    print('DEBUG-------------',role,flush=True)

    publish_user_details(user_id,role)

