from .models import EmployerProfile,JobRequest,Notification
from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
import jwt
from datetime import datetime, timedelta
from django.conf import settings

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



class ChatContactSerializer(serializers.ModelSerializer):
    other_party_name = serializers.SerializerMethodField()
    other_party_image = serializers.SerializerMethodField()
    other_party_user_id = serializers.SerializerMethodField()
    room_name = serializers.SerializerMethodField()
    chat_token = serializers.SerializerMethodField()

    class Meta:
        model = JobRequest
        fields = ['id', 'other_party_name', 'other_party_image', 'other_party_user_id', 'status', 'room_name', 'chat_token']

    def get_other_party_name(self, obj):
        request_user = self.context['request'].user
        if obj.worker.user.user == request_user:
            return obj.employer.company_name
        return obj.worker.user.username

    def get_other_party_image(self, obj):
        request_user = self.context['request'].user
        other_profile = obj.employer.user if obj.worker.user.user == request_user else obj.worker.user
        # build_absolute_uri ensures the full URL (http://...) is sent to the frontend
        return self.context['request'].build_absolute_uri(other_profile.image.url) if other_profile.image else None

    def get_other_party_user_id(self, obj):
        request_user = self.context['request'].user
        if obj.worker.user.user == request_user:
            return obj.employer.user.user.id
        return obj.worker.user.user.id

    def get_room_name(self, obj):
        request_user = self.context['request'].user
        other_id = self.get_other_party_user_id(obj)
        # Always sort IDs to ensure both users land in the same room (e.g., "5_12")
        ids = sorted([request_user.id, other_id])
        return f"{ids[0]}_{ids[1]}"

    def get_chat_token(self, obj):
        request_user = self.context['request'].user
        room_name = self.get_room_name(obj)
        
        # This payload is what the WebSocket Service will verify
        payload = {
            'user_id': request_user.id,
            'room_name': room_name,
            'exp': datetime.utcnow() + timedelta(days=1), # Token valid for 24 hours
            'iat': datetime.utcnow(),
        }
        
        # Use the SECRET_KEY from your settings
        return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')