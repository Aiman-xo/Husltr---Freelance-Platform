from django.shortcuts import render
from .models import Location
from .serializers import LocationSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

# Create your views here.

class LocationView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self,request):
        user_profile = request.user.profile

        try:
            location_instance = Location.objects.get(user = user_profile)
            serializer = LocationSerializer(location_instance,data=request.data)
        except Location.DoesNotExist:
            serializer = LocationSerializer(data= request.data)
        
        if serializer.is_valid():
            serializer.save(user = user_profile)
            return Response(serializer.data,status=status.HTTP_200_OK)
        
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)