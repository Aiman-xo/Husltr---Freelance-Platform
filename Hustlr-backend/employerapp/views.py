from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import EmployerProfile
from .serializers import EmployerProfileSerializer

# Create your views here.

class EmployerProfileSetupView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request):
        user_profile =request.user.profile # => related name
        try:
            employer_obj = user_profile.employer_profile # => related name 
            serializer = EmployerProfileSerializer(employer_obj)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except EmployerProfile.DoesNotExist:
            return Response({"message": "No employer profile found"}, status=status.HTTP_404_NOT_FOUND)
        
    def post(self,request):
        user_profile = request.user.profile # => related name
        employer_obj, created = EmployerProfile.objects.get_or_create(user = user_profile)
        employer_serializer = EmployerProfileSerializer(employer_obj,data = request.data,partial = True)
        if employer_serializer.is_valid():
            employer_serializer.save()
            return Response({"message": "Employer profile updated!"}, status=status.HTTP_200_OK)
        return Response(employer_serializer.errors, status=status.HTTP_400_BAD_REQUEST)