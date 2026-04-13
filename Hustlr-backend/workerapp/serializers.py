from .models import WorkerProfile,Skill
from employerapp.models import JobRequest,JobMaterials
from rest_framework.serializers import ModelSerializer
from django.core.validators import MinValueValidator, MaxValueValidator
from rest_framework import serializers


class WorkerProfileWriteSerializer(serializers.ModelSerializer):
    
    base_Pay = serializers.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(99999)])
    experience = serializers.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(999)])
    hourly_rate = serializers.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(99999)])

    skills = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(),
        many=True
    )

    class Meta:
        model = WorkerProfile
        fields = [
            'base_Pay',
            'job_description',
            'experience',
            'hourly_rate',
            'skills'
        ]

class SkillSerializer(ModelSerializer):
    class Meta:
        model = Skill
        fields=['id','name']


class WorkerProfileReadSerializer(ModelSerializer):
    skills = SkillSerializer(many=True,read_only = True)
    class Meta:
        model = WorkerProfile
        fields = ['base_Pay','job_description','experience','hourly_rate','skills']

class WorkerProfileReadSerializer(ModelSerializer):
    name = serializers.CharField(source='user.username', read_only=True)
    city = serializers.CharField(source='user.city', read_only=True)
    avatar = serializers.ImageField(source='user.image', read_only=True)
    skills = SkillSerializer(many=True, read_only=True)


    class Meta:
        model=WorkerProfile
        fields=[

            'id', 'name', 'avatar', 'city', 'base_Pay', 
            'job_description', 'experience', 'hourly_rate', 'skills'
        ]

class WorkerActiveJobSerializer(ModelSerializer):
    employer_profile_image = serializers.ImageField(source = 'employer.user.image',read_only= True)
    employer_name = serializers.CharField(source = 'employer.company_name',read_only= True)
    class Meta:
        model = JobRequest
        fields =['id','employer','worker','description','city','project_image','status','created_at','employer_profile_image','employer_name',
                 'contract_hourly_rate','estimated_hours','start_time','end_time','is_timer_active']
        extra_kwargs = {
            'employer': {'read_only': True}
        }

class JobMaterialSerializer(ModelSerializer):
    class Meta:
        model = JobMaterials
        fields = '__all__'