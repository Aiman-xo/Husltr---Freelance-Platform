from django.shortcuts import render
from django.core.cache import cache
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import EmployerProfile,JobRequest,Notification, JobMaterials,JobPost,JobBilling
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .serializers import EmployerProfileSerializer,JobRequestSerializer,JobRequestHandleSerializer,ChatContactSerializer,JobPostSerializer,JobBillingSerializer
from .permissions import IsEmployer
from workerapp.permissions import IsWorker

from django.db.models import Q, Max, Sum
from rest_framework.pagination import PageNumberPagination

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

import razorpay
from hustlr import settings
from django.utils import timezone
from authapp.models import HustlrUsers

client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_SECRET_KEY))



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

        serializer = JobRequestSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            
            job_request = serializer.save(employer=employer_profile, is_employer_initiated=True)


            # 2. Get the recipient's User ID
            # worker -> profile -> user relationship
            worker_user = job_request.worker.user.user 
            worker_user_id = worker_user.id
            print('-------VIEW USER ID--------',worker_user_id)

            truncated_desc = (job_request.description[:30] + '..') if len(job_request.description) > 30 else job_request.description
            
            # 3. Create Database Notification (for history)
            Notification.objects.create(
                recipient=worker_user,
                title="New Job Offer",
                message=f"Employer in {job_request.city} have shown interest! Check 'Requests'.",
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

# show all the job requests send by the employer to the worker induvidually.
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
        
        serializer = JobRequestHandleSerializer(result_page, many=True, context={'request': request})
        
        # Use paginator.get_paginated_response to get the 'next', 'previous', and 'count' fields
        response_data = paginator.get_paginated_response(serializer.data).data
        
        cache.set(cache_key, response_data, 60 * 10)
        return Response(response_data, status=status.HTTP_200_OK)

# show job induvidually in the employer side and also perform the tasks like cancel the request and start the work etc..
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
                serializer = JobRequestHandleSerializer(job_request, context={'request': request})
                response_data = serializer.data
                response_data['message'] = message # Attach message to the data

            # --- REAL-TIME NOTIFICATION START ---
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                channel_layer = get_channel_layer()
                
                if action == 'accept_start':
                    worker_user_id = job_request.worker.user.user.id
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
                elif action == 'cancel':
                    worker_user_id = job_request.worker.user.user.id
                    async_to_sync(channel_layer.group_send)(
                        f"user_notifications_{worker_user_id}",
                        {
                            "type": "send_notification",
                            "payload": {
                                "type": "JOB_CANCELLED",
                                "job_id": job_request.id,
                                "new_status": job_request.status,
                                "message": f"Job Request for {job_request.city} has been cancelled by the employer."
                            }
                        }
                    )
            except Exception as e:
                print(f"Failed to send websocket notification: {e}")
            # --- REAL-TIME NOTIFICATION END ---

            # --- CACHE CLEARING START ---
            # Clear all cached versions of the employer's dashboard to ensure immediate updates
            # across all tabs (All, Active, Accepted, etc.) and all pages.
            cache_key_prefix = f"employer_box_{employer_profile_id}"
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(f"{cache_key_prefix}_*")
            else:
                # Fallback: Delete common keys if delete_pattern is not available
                statuses = ['all', 'pending', 'cancelled', 'accepted', 'in_progress', 'completed', 'starting', 'accepted,in_progress,starting,completed']
                for job_status in statuses:
                    for page in range(1, 11): 
                        cache.delete(f'{cache_key_prefix}_{job_status}_page_{page}')
                cache.delete(f"{cache_key_prefix}_all")

            # 2. Clear Worker side 
            worker_id = job_request.worker.id
            cache.delete(f"worker_inbox_{worker_id}")
            # --- CACHE CLEARING END ---

            return Response(response_data, status=status.HTTP_200_OK)

        except JobRequest.DoesNotExist:
            return Response({'error': 'Job request not found or unauthorized'}, status=status.HTTP_404_NOT_FOUND)
        except AttributeError:
            return Response({'error': 'Employer profile not found'}, status=status.HTTP_400_BAD_REQUEST)
        



class EmployerHandleRequestView(APIView):
    permission_classes = [IsAuthenticated, IsEmployer]

    def get(self, request):
        try:
            employer_profile = request.user.profile.employer_profile
            # Only get requests that were initiated by workers (job_post is not null)
            # and are still pending.
            interests = JobRequest.objects.filter(
                employer=employer_profile,
                is_employer_initiated=False,
                status='pending'
            ).select_related('worker__user').order_by('-created_at')

            serializer = JobRequestHandleSerializer(interests, many=True, context={'request': request})
            return Response({'results': serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, request_id):
        # Action should be 'accepted' or 'rejected' sent from frontend
        action = request.data.get('status') 
        
        if action not in ['accepted', 'rejected']:
            return Response({'error': 'Invalid status. Use "accepted" or "rejected".'}, 
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            # 1. Ensure this request belongs to the logged-in employer
            employer_profile = request.user.profile.employer_profile
            job_request = JobRequest.objects.get(id=request_id, employer=employer_profile)

            # 2. Update the status
            job_request.status = action
            
            # LOCK THE RATE if it's not already set (safety fallback)
            if action == 'accepted' and not job_request.contract_hourly_rate:
                job_request.contract_hourly_rate = job_request.worker.hourly_rate
                
            job_request.save()
            
            Notification.objects.create(
                recipient=job_request.worker.user.user,
                title=f"Request {action}",
                message=f"Employer {employer_profile.company_name} has {action} your request for the job you have request in the city {job_request.city}",
                related_id=job_request.id
            )

            # --- REAL-TIME NOTIFICATION ---
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                channel_layer = get_channel_layer()
                worker_user_id = job_request.worker.user.user.id
                async_to_sync(channel_layer.group_send)(
                    f"user_notifications_{worker_user_id}",
                    {
                        "type": "send_notification",
                        "payload": {
                            "type": "INTEREST_UPDATE",
                            "title": f"Request {action}",
                            "job_id": job_request.id,
                            "new_status": action,
                            "message": f"Your interest for job in {job_request.city} has been {action}."
                        }
                    }
                )
            except Exception as e:
                print(f"Failed to send interest update notification: {e}")

            

            # 3. CRITICAL: Clear Caches!
            # Clear worker's inbox and employer's dashboard to reflect status change immediately.
            cache.delete(f"worker_inbox_{job_request.worker.id}")
            
            employer_id = employer_profile.id
            cache_key_prefix = f"employer_box_{employer_id}"
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(f"{cache_key_prefix}_*")
            else:
                statuses = ['all', 'pending', 'cancelled', 'accepted', 'in_progress', 'completed', 'starting', 'accepted,in_progress,starting,completed']
                for job_status in statuses:
                    for page in range(1, 11):
                        cache.delete(f"{cache_key_prefix}_{job_status}_page_{page}")

            return Response({
                'message': f'Request has been {action}.',
                'current_status': job_request.status
            }, status=status.HTTP_200_OK)

        except JobRequest.DoesNotExist:
            return Response({'error': 'Job request not found or you do not have permission.'}, 
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
        
@swagger_auto_schema(
    request_body=JobPostSerializer,
    responses={
        201: openapi.Response(
            "Job Post Successful",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "message": openapi.Schema(type=openapi.TYPE_STRING),
                    "data": openapi.Schema(type=openapi.TYPE_OBJECT),
                },
            ),
        ),
        400: "Bad Request (validation error)",
        500: "Internal server error",
    },
)
class JobPostView(APIView):
    permission_classes=[IsAuthenticated,IsEmployer]
    def post(self,request):
        try:
            employer_profile = request.user.profile.employer_profile
        except AttributeError:
            return Response({'error': 'Employer profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = JobPostSerializer(data=request.data)
        if serializer.is_valid():
            job_post = serializer.save(employer=employer_profile)
            
            # --- TRIGGER AI SYNC START ---
            def trigger_ai_sync():
                import requests
                try:
                    # Point to the ai-service container directly via Docker network
                    # Or use the external URL if needed, but internal is better.
                    requests.post("http://localhost:8002/sync", timeout=10)
                except Exception as e:
                    print(f"AI Sync Trigger Failed: {e}")
            
            import threading
            threading.Thread(target=trigger_ai_sync, daemon=True).start()
            # --- TRIGGER AI SYNC END ---

            return Response({'message':'Job Posted Successfully','data':serializer.data},status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)
    
    def get(self,request):
        try:
            employer_profile = request.user.profile.employer_profile
            jobs_posted = JobPost.objects.filter(employer=employer_profile).select_related('employer').prefetch_related('required_skills').all()

            serializer = JobPostSerializer(jobs_posted,many=True)
            return Response({'message':'fetched jobs!','result':serializer.data},status=status.HTTP_200_OK)
        except AttributeError:
            return Response({'error': 'Employer profile not found.'}, status=status.HTTP_404_NOT_FOUND)
    
class JobPostHandleDelete(APIView):
    permission_classes=[IsAuthenticated,IsEmployer]
    def delete(self,request,post_id):
        try:
            employer_profile = request.user.profile.employer_profile
            deleted_count, _ =JobPost.objects.filter(employer=employer_profile,id=post_id).delete()
            if deleted_count == 0:
                return Response(
                {'error': 'Post not found or you do not have permission to delete it.'}, 
                status=status.HTTP_404_NOT_FOUND
            )
            return Response({'message':'post deleted successfully'},status=status.HTTP_200_OK)
        except AttributeError:
            return Response({'error':'could delete the post'},status=status.HTTP_404_NOT_FOUND)

#---------------------------------------------PAYMENT LOGIC---------------------------------------------------

class CreateRayzorpayClientOrder(APIView):
    permission_classes = [IsAuthenticated,IsEmployer]
    def post(self,request,job_billing_id):
        try:
            billing = JobBilling.objects.get(id=job_billing_id)
            if billing.total_amount is None or billing.total_amount <= 0:
                return Response(
                    {"error": "Invalid amount. Billing total must be greater than zero."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            total_amount = billing.total_amount
            amount_in_paise = int(total_amount*100)

            data = {
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": f"job_rcpt_{billing.id}",
            "notes": {
                "job_id": billing.job.id,
                "billing_id": billing.id
                }
            }
        
            razorpay_order = client.order.create(data=data)

            billing.razorpay_order_id = razorpay_order['id']
            billing.save()

            return Response({
                "order_id": razorpay_order['id'],
                "amount": amount_in_paise,
                "currency": "INR",
                "key_id": settings.RAZORPAY_API_KEY
            },status=status.HTTP_201_CREATED)
        
        except JobBilling.DoesNotExist:
            return Response({"error": "Billing record not found"}, status=404)
        except Exception as e:
            # Catch network errors or Razorpay API errors
            return Response({"error": str(e)}, status=500)
        
class RayzorpayVerifyClientOrder(APIView):
    permission_classes = [IsAuthenticated,IsEmployer]
    def post(self,request):

        order_id = request.data.get('razorpay_order_id')
        payment_id = request.data.get('razorpay_payment_id')
        signature = request.data.get('razorpay_signature')

        data_to_verify = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }

        try:
            client.utility.verify_payment_signature(data_to_verify)

            billing = JobBilling.objects.get(razorpay_order_id=order_id)
            billing.is_paid = True
            billing.razorpay_payment_id = payment_id
            billing.paid_at = timezone.now()
            billing.save()

            # Clear dashboard cache for both Employer and Worker so "Paid" status reflects immediately
            from django.core.cache import cache
            employer_id = billing.job.employer.id
            worker_id = billing.job.worker.id
            
            # Clear all cached versions of the employer's dashboard
            cache_key_prefix = f"employer_box_{employer_id}"
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(f"{cache_key_prefix}_*")
            else:
                # Comprehensive fallback for all possible tabs and pages
                statuses = ['all', 'completed', 'in_progress', 'accepted', 'starting', 'accepted,in_progress,starting,completed']
                for s in statuses:
                    for p in range(1, 11):
                        cache.delete(f"{cache_key_prefix}_{s}_page_{p}")
            
            # Also clear worker inbox just in case
            cache.delete(f"worker_inbox_{worker_id}")

            # --- REAL-TIME NOTIFICATION START ---
            # Notify the Worker that they have been paid!
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                channel_layer = get_channel_layer()
                
                # We need the user ID associated with the worker
                worker_user_id = billing.job.worker.user.id 
                
                async_to_sync(channel_layer.group_send)(
                    f"user_notifications_{worker_user_id}",
                    {
                        "type": "send_notification",
                        "payload": {
                            "type": "PAYMENT_RECEIVED",
                            "job_id": billing.job.id,
                            # "title": "Payment Received! 💰",
                            "message": f"Employer paid ₹{billing.total_amount} for '{billing.job.title}'."
                        }
                    }
                )
            except Exception as e:
                print(f"FAILED TO SEND PAYMENT NOTIFICATION: {e}")
            # --- REAL-TIME NOTIFICATION END ---

            return Response({
                "message": "Payment verified successfully",
                "billing_id": billing.id
            }, status=status.HTTP_200_OK)

        except razorpay.errors.SignatureVerificationError:
            return Response({"error": "Signature verification failed"}, status=400)
        except JobBilling.DoesNotExist:
            return Response({"error": "Billing record not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class EmployerPaymentHistoryView(APIView):
    permission_classes = [IsAuthenticated, IsEmployer]
    def get(self, request):
        try:
            # Safer, more direct way to filter for the specific employer
            employer = request.user.profile.employer_profile
            billings = JobBilling.objects.filter(job__employer=employer, is_paid=True).order_by('-paid_at')
            serializer = JobBillingSerializer(billings, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class PlatformStatsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            # 1. Total number of users
            total_users = HustlrUsers.objects.count()

            # 2. Total jobs completed
            jobs_completed = JobRequest.objects.filter(status='completed').count()

            # 3. Number of active jobs right now
            active_jobs = JobRequest.objects.filter(status__in=['accepted', 'starting', 'in_progress']).count()

            # 4. Total payouts (amount generated)
            total_payouts_dict = JobBilling.objects.filter(is_paid=True).aggregate(Sum('total_amount'))
            total_payouts = total_payouts_dict['total_amount__sum'] or 0

            return Response({
                "total_users": total_users,
                "jobs_completed": jobs_completed,
                "active_jobs": active_jobs,
                "total_payouts": float(total_payouts),
                "average_rating": 4.9 # Keeping static for now as requested
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)