from .models import EmployerProfile,JobRequest,Notification
from rest_framework.serializers import ModelSerializer
from rest_framework import serializers

class EmployerProfileSerializer(ModelSerializer):
    class Meta:
        model = EmployerProfile
        fields = ['company_name']

class JobRequestSerializer(ModelSerializer):
    employer_profile_image = serializers.ImageField(source = 'employer.user.image',read_only= True)
    employer_name = serializers.CharField(source = 'employer.company_name',read_only= True)
    class Meta:
        model = JobRequest
        fields =['id','employer','worker','description','city','project_image','status','created_at','employer_profile_image','employer_name']
        extra_kwargs = {
            'employer': {'read_only': True}
        }


class JobRequestHandleSerializer(ModelSerializer):
    worker_profile_image = serializers.ImageField(source = 'worker.user.image',read_only=True)
    worker_name = serializers.CharField(source = 'worker.user.username',read_only=True)
    base_pay = serializers.IntegerField(source = 'worker.base_Pay',read_only=True)
    hourly_rate = serializers.IntegerField(source = 'worker.hourly_rate',read_only=True)
    class Meta:
        model = JobRequest
        fields =['id','employer','worker','worker_profile_image','worker_name',
                 'base_pay','hourly_rate','description','city','project_image','status','created_at']
        extra_kwargs = {
            'employer': {'read_only': True}
        }

class NotificationSerializer(ModelSerializer):
    class Meta:
        model = Notification
        fields='__all__'