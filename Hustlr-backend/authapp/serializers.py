from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from .models import HustlrUsers,Profile,ResetPassword
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

import random
import re
from django.utils import timezone
from django.db import transaction

class CreateUserSerializer(ModelSerializer):
    confirm_password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=Profile.ROLE_CHOICES,write_only=True)
    email = serializers.EmailField()
    class Meta:
        model = HustlrUsers
        fields = ['email','password','confirm_password','role']

    def validate(self,data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")

        try:
            validate_password(data['password'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({'password':e.messages})
        return data

        

    def validate_email(self,email):
        if not re.match(r"^[a-zA-Z0-9._%+-]+@([a-zA-Z0-9-]{2,}\.)+[a-zA-Z]{2,}$", email):
            raise serializers.ValidationError("Enter a valid email address with a proper domain (e.g. gmail.com)")
        if HustlrUsers.objects.filter(email=email).exists():
            raise serializers.ValidationError("Email already exists")
        return email

    def create(self,validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        role = validated_data.pop('role')
        with transaction.atomic():
            user = HustlrUsers.objects.create_user(password=password,is_superuser=False,
                is_staff=False,**validated_data)

            if not role:
                raise serializers.ValidationError('please select a role!')

            Profile.objects.create(
                user=user,
                active_role = role
            )

        return user
    

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        style={'input_type': 'password'}, 
        trim_whitespace=False,
        required=True
    )

    def validate_email(self, email):
        if not re.match(r"^[a-zA-Z0-9._%+-]+@([a-zA-Z0-9-]{2,}\.)+[a-zA-Z]{2,}$", email):
            raise serializers.ValidationError("Enter a valid email address with a proper domain (e.g. gmail.com)")
        return email





class ResetPasswordSerializer(serializers.Serializer):
    reset_session = serializers.CharField()
    new_password = serializers.CharField(write_only = True)
    confirm_password = serializers.CharField(write_only = True)

    def validate(self,data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password":'passwords did not match'})
        

        try:
            validate_password(data['new_password'])
        except DjangoValidationError as e :
            raise serializers.ValidationError({'new_password':e.messages}) 
        
        return data
    
class VerifyOTPSerializer(serializers.Serializer):
    entered_otp = serializers.CharField(write_only=True)
    reset_session = serializers.CharField()

    def validate(self, data):
        entered_otp = data['entered_otp']
        reset_session = data['reset_session']

        try:
            otp_obj = ResetPassword.objects.get(reset_session = reset_session)
        except ResetPassword.DoesNotExist:
            raise serializers.ValidationError('Invalid session')
        
        if otp_obj.is_expired():
            raise serializers.ValidationError({'entered_otp':"OTP has expired"})
        
        if otp_obj.otp != entered_otp:
            raise serializers.ValidationError({'entered_otp':'OTP did not match'})
        
        data['otp_obj'] = otp_obj
        return data
    
class GenerateOTPserializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self,value):
        user = HustlrUsers.objects.filter(email = value).first()
        if not user:
            raise serializers.ValidationError({'email':"couldn't fetch user"})
        
        self.user = user
        return value
    
    def create(self, validated_data):
        otp = random.randint(100000,999999)

        session, _ = ResetPassword.objects.update_or_create(
            user = self.user,
            defaults={
                'otp': otp,
                'is_verified': False,
                'created_at': timezone.now()
            }
        )

        return session    

class ProfileSetupSerializer(ModelSerializer):
    class Meta:
        model = Profile
        fields = ['user','image','city','phone_number','username']

    
