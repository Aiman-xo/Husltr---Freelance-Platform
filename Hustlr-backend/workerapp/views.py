from django.shortcuts import render
from django.core.cache import cache
from django.db.models import Q

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

import logging

from .permissions import IsWorker
from .models import WorkerProfile,Skill
from .serializers import WorkerProfileReadSerializer,SkillSerializer,WorkerProfileWriteSerializer,WorkerActiveJobSerializer,JobMaterialSerializer
from employerapp.serializers import JobRequestSerializer,NotificationSerializer
from employerapp.models import JobRequest,Notification,JobMaterials
from employerapp.permissions import IsEmployer

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
        
class GetActiveJobs(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    def get(self, request):
        active_statuses = ['starting', 'accepted', 'in_progress', 'completed']
        
        try:
            # We filter jobs where the worker is the one logged in
            active_jobs = JobRequest.objects.filter(
                worker__user__user=request.user, 
                status__in=active_statuses
            ).select_related('employer__user').order_by('-created_at')
            
            # If no jobs found, it just returns an empty list [], which is better than an error
            serializer = WorkerActiveJobSerializer(active_jobs, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class HandleJobRequestView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    def post(self, request, jobRequestId):
        # 1. Get the action from the frontend (expecting 'accept' or 'reject')
        action = request.data.get('action')
        
        if action not in ['accept', 'reject', 'start', 'finish']:
            return Response({'error': f'Invalid action: {action}'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            # Secure lookup: Current user must be the assigned Worker
            job_req = JobRequest.objects.get(
                pk=jobRequestId, 
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
            job_req.contract_hourly_rate = job_req.worker.hourly_rate
            message = "Job accepted and rate locked."
        elif action == 'reject':
            job_req.status = 'rejected'
            message = "Job rejected."
        elif action == 'start':
            if job_req.status != 'accepted':
                return Response({'error': 'You can only start an accepted job.'}, status=400)
            job_req.status = 'starting'
            message = "Job start requested. Waiting for employer acceptance."
        elif action == 'finish':
            if job_req.status != 'in_progress':
                return Response({'error': 'You can only finish a job that is in progress.'}, status=400)
            
            from django.utils import timezone
            from decimal import Decimal
            
            job_req.status = 'completed'
            job_req.end_time = timezone.now()
            job_req.is_timer_active = False
            
            # Billing Calculation
            duration = job_req.end_time - job_req.start_time
            total_seconds = Decimal(duration.total_seconds())
            hours = total_seconds / Decimal(3600)
            
            base_pay = Decimal(job_req.worker.base_Pay or 0)
            hourly_rate = Decimal(job_req.contract_hourly_rate or job_req.worker.hourly_rate or 0)

            # Logic: Always give base_pay. After 1 hour, add hourly_rate for extra time.
            if hours <= 1:
                labor_amount = base_pay
            else:
                labor_amount = base_pay + (hours - 1) * hourly_rate
            
            from employerapp.models import JobBilling
            billing, created = JobBilling.objects.get_or_create(job=job_req)
            billing.labor_amount = labor_amount
            material_amount = Decimal(request.data.get('material_amount', 0))
            billing.material_amount = material_amount
            billing.total_amount = labor_amount + material_amount
            
            # Handle Bill Image upload
            bill_image = request.FILES.get('bill_image')
            if bill_image:
                billing.bill_image = bill_image
                
            billing.save()
            
            message = "Job completed and billing calculated."
        
        job_req.save()
        
        # Fresh data for the frontend
        serializer = WorkerActiveJobSerializer(job_req, context={'request': request})
        response_data = serializer.data
        response_data['message'] = message

        # --- REAL-TIME NOTIFICATION START ---
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            
            # Notify the Employer
            employer_user_id = job_req.employer.user.user.id
            payload_type = f"JOB_{action.upper()}"
            if action == 'start': payload_type = "JOB_STARTING"
            if action == 'finish': payload_type = "JOB_COMPLETED"
            
            async_to_sync(channel_layer.group_send)(
                f"user_notifications_{employer_user_id}",
                {
                    "type": "send_notification",
                    "payload": {
                        "type": payload_type,
                        "title": "Job Update" if action != 'start' else "Start Request!",
                        "job_id": job_req.id,
                        "new_status": job_req.status,
                        "message": message,
                        "timestamp": timezone.now().isoformat() if action == 'finish' else job_req.created_at.isoformat()
                    }
                }
            )
        except Exception as e:
            logger.error(f"Failed to send websocket notification: {e}")
        # --- REAL-TIME NOTIFICATION END ---

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

        return Response(response_data, status=status.HTTP_200_OK)
    
    def patch(self, request, jobRequestId):
        try:
            job = JobRequest.objects.get( pk=jobRequestId, worker__user__user=request.user)
        except JobRequest.DoesNotExist:
            return Response({'error':'cannot get the Job'},status=status.HTTP_400_BAD_REQUEST)
        if job.status != 'accepted':
            return Response({'error': 'You can only set estimates for accepted jobs.'}, status=400)
        estimate = request.data.get('estimated_hours')
        
        if estimate:
            job.estimated_hours = float(estimate)
            job.save()
            return Response({"message": "Estimate updated", "estimated_hours": job.estimated_hours})
        return Response({"error": "Invalid estimate"}, status=400)
    

class GetNotificationView(APIView):
    permission_classes = [IsAuthenticated,IsWorker]

    def get(self, request):
        try:
            # 1. Fetch notifications for the current user
            # We use recipient=request.user because your model links to HustlrUsers
            notifications = Notification.objects.select_related('recipient').filter(recipient=request.user)
            serializer = NotificationSerializer(notifications, many=True)
            unread_notification = notifications.filter(is_read=False).count()

            return Response({

                'result':serializer.data,
                'unread_count':unread_notification

                }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": "Failed to fetch notifications"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self,request):
        unread_notifications = Notification.objects.select_related('recipient').filter(recipient=request.user,is_read = False)

        # 2. Check if there are any to update
        if not unread_notifications.exists():
            return Response(
                {'message': 'No unread notifications to mark.'}, 
                status=status.HTTP_200_OK
            )
        
        unread_notifications.update(is_read=True)   
        return Response ({'message':'All notifications Changed as read successfully!'},status=status.HTTP_200_OK)
    
# Job note taking view

class JobMaterialsView(APIView):
    permission_classes = [IsAuthenticated,IsWorker]
    
    def post(self,request):
        data = request.data
        
        if not isinstance(data, list):
            return Response({'error': 'Expected a list of items'}, status=status.HTTP_400_BAD_REQUEST)
        if not data:
            return Response({'error': 'List is empty'}, status=status.HTTP_400_BAD_REQUEST)
        
        job_id = data[0].get('job')
        try:
            JobRequest.objects.get(id = job_id,worker__user__user = request.user)
        except (JobRequest.DoesNotExist):
            return Response({'error':'couldnt fetch job'},status=status.HTTP_400_BAD_REQUEST)
        
        serializer = JobMaterialSerializer(data = request.data,many=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'message':'Note created!'},status=status.HTTP_200_OK)
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)
    
class SeeJobMaterialsView(APIView):
    permission_classes = [IsAuthenticated,(IsWorker | IsEmployer)]
    def get(self, request,job_id):
        
        if not job_id:
            return Response({'error': 'job_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Correct the filter path and use .order_by()
        notes = JobMaterials.objects.filter(
            Q(job=job_id) & (
                
            Q(job__worker__user__user=request.user) | Q(job__employer__user__user=request.user)

            )).order_by('-created_at') 

        serializer = JobMaterialSerializer(notes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)