from .models import WorkerProfile,Skill
from rest_framework.serializers import ModelSerializer
from rest_framework import serializers


class WorkerProfileWriteSerializer(serializers.ModelSerializer):
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