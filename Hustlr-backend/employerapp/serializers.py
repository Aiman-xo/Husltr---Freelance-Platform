from .models import EmployerProfile
from rest_framework.serializers import ModelSerializer

class EmployerProfileSerializer(ModelSerializer):
    class Meta:
        model = EmployerProfile
        fields = ['company_name']