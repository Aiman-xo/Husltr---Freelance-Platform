from workerapp.models import WorkerProfile
from workerapp.serializers import SkillSerializer
from employerapp.models import EmployerProfile, JobRequest, JobBilling
from rest_framework import serializers


class GetWorkerAdminSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username',read_only=True)
    city = serializers.CharField(source='user.city',read_only=True)
    profile_pic = serializers.ImageField(source='user.image',read_only=True)
    phone_number = serializers.CharField(source='user.phone_number',read_only=True)
    is_active = serializers.BooleanField(source='user.user.is_active')
    skills = SkillSerializer(many=True,read_only=True)
    class Meta:
        model = WorkerProfile
        fields=[
            'id', 'username', 'city', 'base_Pay', 
            'job_description', 'experience', 'hourly_rate', 'skills','is_active','phone_number','profile_pic'
        ]

class GetEmployerAdminSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username',read_only=True)
    city = serializers.CharField(source='user.city',read_only=True)
    profile_pic = serializers.ImageField(source='user.image',read_only=True)
    phone_number = serializers.CharField(source='user.phone_number',read_only=True)
    is_active = serializers.BooleanField(source='user.user.is_active')

    class Meta:
        model=EmployerProfile
        fields=['id','company_name','username','city','phone_number','profile_pic','is_active']

class JobAdminSerializer(serializers.ModelSerializer):
    employer_company = serializers.CharField(source='employer.company_name', read_only=True)
    worker_name = serializers.CharField(source='worker.user.username', read_only=True)
    
    class Meta:
        model = JobRequest
        fields = ['id', 'description', 'employer_company', 'worker_name', 'status', 'created_at', 'contract_hourly_rate']

class FinancialAdminSerializer(serializers.ModelSerializer):
    job_id = serializers.IntegerField(source='job.id', read_only=True)
    employer_name = serializers.CharField(source='job.employer.company_name', read_only=True)
    worker_name = serializers.CharField(source='job.worker.user.username', read_only=True)
    status = serializers.CharField(source='job.status', read_only=True)

    class Meta:
        model = JobBilling
        fields = ['id', 'job_id', 'employer_name', 'worker_name', 'total_amount', 'submitted_at', 'status']