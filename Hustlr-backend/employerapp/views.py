from django.shortcuts import render
from django.core.cache import cache
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import EmployerProfile,JobRequest,Notification, JobMaterials
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .serializers import EmployerProfileSerializer,JobRequestSerializer,JobRequestHandleSerializer,ChatContactSerializer
from .permissions import IsEmployer
from workerapp.permissions import IsWorker

from django.db.models import Q,Max
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

            truncated_desc = (job_request.description[:30] + '..') if len(job_request.description) > 30 else job_request.description
            # 3. Create Database Notification (for history)
            Notification.objects.create(
                recipient=worker_user,
                title=f"New Request : {truncated_desc}",
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
            status_list = status_filter.split(',')
            queryset = queryset.filter(status__in=status_list)

        paginator = PageNumberPagination()
        paginator.page_size = 10  # Increase for better dashboard view
        
        # Paginate the queryset
        result_page = paginator.paginate_queryset(queryset, request)
        
        serializer = JobRequestHandleSerializer(result_page, many=True)
        
        # Use paginator.get_paginated_response to get the 'next', 'previous', and 'count' fields
        response_data = paginator.get_paginated_response(serializer.data).data
        
        cache.set(cache_key, response_data, 60 * 10)
        return Response(response_data, status=status.HTTP_200_OK)

class JobRequestInduvidualHandleView(APIView):
    permission_classes=[IsAuthenticated,IsEmployer]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get(self, request, jobRequestId):
        try:
            employer_profile_id = request.user.profile.employer_profile.id
            job_req = JobRequest.objects.select_related('worker__user', 'employer__user').get(
                pk=jobRequestId, 
                employer_id=employer_profile_id
            )
            serializer = JobRequestHandleSerializer(job_req, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except JobRequest.DoesNotExist:
            return Response({'error': 'Job request not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def post(self,request,jobRequestId):
        try:
            employer_profile_id = request.user.profile.employer_profile.id
        except Exception as e:
            return Response({'error':f'{e}'})
        
        action = request.data.get('action', 'cancel')
        
        try:
            with transaction.atomic():
                job_request = JobRequest.objects.get(pk=jobRequestId,employer_id = employer_profile_id)
                
                if action == 'cancel':
                    if job_request.status != 'pending':
                        return Response({'error': f'Cannot cancel a request that is already {job_request.status}'}, status=400)
                    job_request.status = 'cancelled'
                    message = 'Request cancelled successfully'
                elif action == 'accept_start':
                    if job_request.status != 'starting':
                        return Response({'error': f'Cannot accept start for a job that is {job_request.status}'}, status=400)
                    
                    from django.utils import timezone
                    job_request.status = 'in_progress'
                    job_request.start_time = timezone.now()
                    job_request.is_timer_active = True
                    message = 'Job started successfully'
                else:
                    return Response({'error': f'Invalid action: {action}'}, status=400)
                
                job_request.save()
                
                # Fetch fresh data to ensure all related fields are present
                serializer = JobRequestHandleSerializer(job_request)
                response_data = serializer.data
                response_data['message'] = message # Attach message to the data

            # --- REAL-TIME NOTIFICATION START ---
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                if action == 'accept_start':
                    worker_user_id = job_request.worker.user.user.id
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f"user_notifications_{worker_user_id}",
                        {
                            "type": "send_notification",
                            "payload": {
                                "type": "JOB_IN_PROGRESS",
                                "job_id": job_request.id,
                                "new_status": job_request.status,
                                "start_time": job_request.start_time.isoformat(),
                                "message": message
                            }
                        }
                    )
            except Exception as e:
                print(f"Failed to send websocket notification: {e}")
            # --- REAL-TIME NOTIFICATION END ---

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

            return Response(response_data, status=status.HTTP_200_OK)

        except JobRequest.DoesNotExist:
            return Response({'error': 'Job request not found or unauthorized'}, status=status.HTTP_404_NOT_FOUND)
        except AttributeError:
            return Response({'error': 'Employer profile not found'}, status=status.HTTP_400_BAD_REQUEST)

ACTIVE_WORK_STATUSES = ['accepted', 'starting', 'in_progress', 'completed']
class ChatListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Get all accepted jobs for the current user
        queryset = JobRequest.objects.filter(
            status__in = ACTIVE_WORK_STATUSES
        ).filter(
            Q(employer__user__user=request.user) | Q(worker__user__user=request.user)
        )

        # 2. Group by employer and worker to find the latest interaction
        # This prevents the "triple Jamal Musiala" issue
        unique_chat_ids = queryset.values('employer', 'worker').annotate(
            latest_id=Max('id')
        ).values_list('latest_id', flat=True)

        # 3. Fetch the actual objects using the IDs we found
        accepted_contacts = JobRequest.objects.filter(
            id__in=unique_chat_ids
        ).select_related(
            'employer__user__user', 
            'worker__user__user'
        ).order_by('-id')

        serializer = ChatContactSerializer(
            accepted_contacts, 
            many=True, 
            context={'request': request}
        )
        
        return Response(serializer.data,status=status.HTTP_200_OK)

class MaterialToggleView(APIView):
    permission_classes = [IsAuthenticated, IsEmployer]
    
    def post(self, request, materialId):
        try:
            employer_profile = request.user.profile.employer_profile
            material = JobMaterials.objects.get(id=materialId, job__employer=employer_profile)
            
            material.is_available_at_site = not material.is_available_at_site
            material.save()
            
            # Notify the Worker
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                worker_user_id = material.job.worker.user.user.id
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f"user_notifications_{worker_user_id}",
                    {
                        "type": "send_notification",
                        "payload": {
                            "type": "MATERIAL_TOGGLE",
                            "job_id": material.job.id,
                            "material_id": material.id,
                            "is_available_at_site": material.is_available_at_site,
                            "message": f"Material '{material.item_description}' status updated by employer."
                        }
                    }
                )
            except Exception as e:
                print(f"Failed to send material toggle notification: {e}")

            return Response({
                'id': material.id,
                'message': 'Material status updated',
                'is_available_at_site': material.is_available_at_site
            }, status=status.HTTP_200_OK)
            
        except JobMaterials.DoesNotExist:
            return Response({'error': 'Material not found or unauthorized'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)