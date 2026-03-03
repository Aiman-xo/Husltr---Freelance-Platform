from django.shortcuts import render
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import EmployerProfile,JobRequest,Notification
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import EmployerProfileSerializer,JobRequestSerializer,JobRequestHandleSerializer
from .permissions import IsEmployer

from django.db.models import Q
from rest_framework.pagination import PageNumberPagination

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


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



class JobRequestView(APIView):
    permission_classes = [IsAuthenticated,IsEmployer]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        try:
            employer_profile = request.user.profile.employer_profile
        except AttributeError:
            return Response({"error": "Only employers can send requests"}, status=status.HTTP_403_FORBIDDEN)

        serializer = JobRequestSerializer(data=request.data)

        if serializer.is_valid():
            
            job_request = serializer.save(employer=employer_profile)


            # 2. Get the recipient's User ID
            # Assuming worker -> profile -> user relationship
            worker_user = job_request.worker.user.user 
            worker_user_id = worker_user.id
            print('-------VIEW USER ID--------',worker_user_id)

            # 3. Create Database Notification (for history)
            Notification.objects.create(
                recipient=worker_user,
                title="New Job Request",
                message=f"You received a request from {employer_profile.company_name}",
                related_id=job_request.id
            )

            # 4. Trigger Real-time WebSocket Notification
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_notifications_{worker_user_id}", # Target group in websocket service
                {
                    "type": "send_notification", # Matches method in your Consumer
                    "payload": {
                        "type": "NEW_JOB_REQUEST",
                        "title": "New Job Request!",
                        "message": f"New request from {employer_profile.company_name}",
                        "job_id": job_request.id,
                        "timestamp": job_request.created_at.isoformat()
                    }
                }
            )
            # We target the specific worker's inbox key
            # Since 'worker' is a ForeignKey, job_request.worker is the WorkerProfile instance
            worker_id = job_request.worker.id
            # cache_key = f"worker_inbox_{worker_id}"
            cache_keys = [
                f'employer_box_{employer_profile.id}_all',
                f'employer_box_{employer_profile.id}_pending',
                f'employer_box_{employer_profile.id}_cancelled',
                f'employer_box_{employer_profile.id}_accepted',
                f"worker_inbox_{worker_id}"
            ]
            cache.delete_many(cache_keys)
            

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class JobRequestHandleView(APIView):
    permission_classes = [IsAuthenticated, IsEmployer]
    
    def get(self, request):
        try:
            employer_profile_id = request.user.profile.employer_profile.id
        except AttributeError:
            return Response({'error': 'Employer profile not found!'}, status=status.HTTP_400_BAD_REQUEST)
        
        status_filter = request.query_params.get('status') 
        page_number = request.query_params.get('page', 1) 

        # 1. Update Cache Key to include page number
        cache_key = f'employer_box_{employer_profile_id}_{status_filter or "all"}_page_{page_number}'

        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data, status=200)

        # 2. Fetch Data
        queryset = JobRequest.objects.filter(
            employer_id=employer_profile_id
        ).select_related('worker__user').order_by('-created_at')

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        paginator = PageNumberPagination()
        paginator.page_size = 5  # Or whatever size you prefer
        
        # Paginate the queryset
        result_page = paginator.paginate_queryset(queryset, request)
        
        serializer = JobRequestHandleSerializer(result_page, many=True)
        
        # Use paginator.get_paginated_response to get the 'next', 'previous', and 'count' fields
        response_data = paginator.get_paginated_response(serializer.data).data
        
        cache.set(cache_key, response_data, 60 * 10)
        return Response(response_data, status=status.HTTP_200_OK)

class JobRequestInduvidualHandleView(APIView):
    permission_classes=[IsAuthenticated,IsEmployer]
    def post(self,request,jobRequestId):
        try:
            employer_profile_id = request.user.profile.employer_profile.id
        except Exception as e:
            return Response({'error':f'{e}'})
        
        try:
            job_request = JobRequest.objects.get(pk=jobRequestId,employer_id = employer_profile_id)
            job_request.status = 'cancelled'
            job_request.save()

            # --- CACHE CLEARING START ---
            # 1. Clear Employer side (all pages/statuses)
            # We use a loop or delete_pattern to ensure we catch those '_page_X' suffixes
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(f"employer_box_{employer_profile_id}_*")
            else:
                # Manual fallback for common pages if delete_pattern isn't available
                keys_to_delete = []
                for job_status in ['all', 'pending', 'cancelled', 'accepted']:
                    for page in range(1, 5): # Clears first 5 pages
                        keys_to_delete.append(f'employer_box_{employer_profile_id}_{job_status}_page_{page}')
                cache.delete_many(keys_to_delete)

            # 2. Clear Worker side 
            # If the worker has pagination too, use a pattern here as well!
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(f"worker_inbox_{job_request.worker_id}_*")
            else:
                cache.delete(f'worker_inbox_{job_request.worker_id}') 
            # --- CACHE CLEARING END ---

            return Response({'message': 'Request cancelled successfully'}, status=status.HTTP_200_OK)

        except JobRequest.DoesNotExist:
            return Response({'error': 'Job request not found or unauthorized'}, status=status.HTTP_404_NOT_FOUND)
        except AttributeError:
            return Response({'error': 'Employer profile not found'}, status=status.HTTP_400_BAD_REQUEST)



