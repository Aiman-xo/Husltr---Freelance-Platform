from django.shortcuts import render
from django.core.cache import cache
from django.db.models import Q

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

import logging

from .permissions import IsWorker
from .models import WorkerProfile,Skill
from .serializers import WorkerProfileReadSerializer,SkillSerializer,WorkerProfileWriteSerializer
from employerapp.serializers import JobRequestSerializer,NotificationSerializer
from employerapp.models import JobRequest,Notification

# Create your views here.

class WorkerProfileSetupView(APIView):
    permission_classes = [IsAuthenticated,IsWorker]
    def get_serializer_class(self):
        if self.request.method in ['POST', 'PUT', 'PATCH']:
            return WorkerProfileWriteSerializer
        return WorkerProfileReadSerializer
    def get(self,request):
        user_profile = request.user.profile
        try:
            worker_obj = user_profile.worker_profile
            serializer = WorkerProfileReadSerializer(worker_obj)
            return Response(serializer.data,status=status.HTTP_200_OK)
        except WorkerProfile.DoesNotExist:
            return Response({"message": "No worker profile found"}, status=status.HTTP_404_NOT_FOUND)

    
    def post(self,request):
        user_profile = request.user.profile
        # 1. Look for an existing profile (don't create it yet!)
        worker_obj = WorkerProfile.objects.filter(user=user_profile).first()
        
        # 2. If worker_obj is None, serializer performs a CREATE.
        # If worker_obj exists, serializer performs an UPDATE.
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(worker_obj, data=request.data, partial=True)
        
        if serializer.is_valid():
            # 3. If it's a new profile, we MUST provide the user during save
            if not worker_obj:
                serializer.save(user=user_profile)
            else:
                serializer.save()
                
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class SkillView(APIView):
    permission_classes=[IsAuthenticated,IsWorker]
    def get(self, request):
        query = request.query_params.get('search', '')

        if query:
            skills = Skill.objects.filter(Q(name__icontains=query))
        else:
            # 3. If no search term, return everything or a limited set
            skills = Skill.objects.all()[:5] 

        serializer = SkillSerializer(skills, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self,request):
        serializer = SkillSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data,status=status.HTTP_200_OK)
        
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)
    
class WorkerListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Start with the base queryset
        workers = WorkerProfile.objects.select_related('user').prefetch_related('skills').all()

        search_query = request.query_params.get('search', None)
        if search_query:
            workers = workers.filter(
                Q(job_description__icontains=search_query) |
                Q(user__username__icontains=search_query) |
                Q(skills__name__icontains=search_query)
            ).distinct()

        try:
            page = int(request.query_params.get('page', 1))
            page_size = 4
        except ValueError:
            page = 1

        start = (page - 1) * page_size
        end = start + page_size
        
        total_count = workers.count()
        paginated_workers = workers[start:end]
        serializer = WorkerProfileReadSerializer(paginated_workers, many=True)

        return Response({
            "count": total_count,
            "next": page + 1 if end < total_count else None,
            "previous": page - 1 if start > 0 else None,
            "results": serializer.data
        }, status=status.HTTP_200_OK)
    
    
logger = logging.getLogger(__name__)
class JobInboxView(APIView):
    permission_classes = [IsAuthenticated,IsWorker]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):

        try:

            worker_profile = request.user.profile.worker_profile
            worker_id = worker_profile.id
        except AttributeError:
            return Response({'error':'worker profile not found!'},status=status.HTTP_400_BAD_REQUEST)
        # We create a unique key for THIS worker
        cache_key = f"worker_inbox_{worker_id}"
        
        # Try to get data from Redis
        try:
            cached_data = cache.get(cache_key)
            
            if cached_data:
                print("--- CACHE HIT: Returning data from Redis ---")
                logger.info('cache succcess!')
                return Response(cached_data,status=status.HTTP_200_OK)
        except Exception as e:
            print("!!! REDIS IS DOWN - CHECKING LOG FILE !!!")
            logger.error(f'Redis crashed{e}')

        
        print("--- CACHE MISS: Fetching from Database ---")

        try:
            # If not in Redis, go to the Database
            active_statuses = ['pending', 'accepted', 'rejected']
            requests = request.user.profile.worker_profile.received_job_offers.filter(
                status__in=active_statuses
            ).order_by('-created_at') # Always good to show newest first!
            serializer = JobRequestSerializer(requests, many=True)
            data = serializer.data
            
            # Store in Redis for 15 minutes
            cache.set(cache_key, data, 60 * 15)
            
            return Response(data,status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error':'Something went wrong!'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        



class HandleJobRequestView(APIView):
    def post(self, request, jobRequestId):
        # 1. Get the action from the frontend (expecting 'accept' or 'reject')
        action = request.data.get('action')
        
        if action not in ['accept', 'reject']:
            return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 2. Secure lookup: Must be 'pending' AND current user must be the Worker
            job_req = JobRequest.objects.get(
                pk=jobRequestId, 
                status='pending',
                worker__user__user=request.user 
            )
        except JobRequest.DoesNotExist:
            return Response(
                {'error': 'Job not found or you are not the assigned worker.'}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # 3. Update based on the action
        if action == 'accept':
            job_req.status = 'accepted'
            message = "Job accepted!"
        else:
            job_req.status = 'rejected'
            message = "Job rejected."

        job_req.save()

        # --- CACHE INVALIDATION LOGIC START ---
        try:
            worker_id = job_req.worker.id
            employer_profile_id = job_req.employer.id  # Get the employer from the job request

            # 1. Clear Worker side
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(f"worker_inbox_{worker_id}")
            else:
                cache.delete(f"worker_inbox_{worker_id}")

            # 2. Clear Employer side (The missing piece!)
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(f"employer_box_{employer_profile_id}_*")
            else:
                # Fallback loop if delete_pattern isn't available
                for job_status in ['all', 'pending', 'cancelled', 'accepted', 'rejected']:
                    for page in range(1, 5):
                        cache.delete(f'employer_box_{employer_profile_id}_{job_status}_page_{page}')

            print(f"--- CACHES DELETED for Worker {worker_id} and Employer {employer_profile_id} ---")
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
        # --- CACHE INVALIDATION LOGIC END ---

        return Response({'message': message, 'new_status': job_req.status}, status=status.HTTP_200_OK)
    

class GetNotificationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # 1. Fetch notifications for the current user
            # We use recipient=request.user because your model links to HustlrUsers
            notifications = Notification.objects.filter(recipient=request.user)
            serializer = NotificationSerializer(notifications, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": "Failed to fetch notifications"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )