from django.shortcuts import render
from workerapp.models import WorkerProfile
from employerapp.models import EmployerProfile, JobRequest, JobPost, JobBilling
from authapp.models import Profile, HustlrUsers
from rest_framework.views import APIView
from .permissions import IsAdmin
from rest_framework.permissions import IsAuthenticated,IsAdminUser

from django.db.models import Sum, Count, Q
from django.core.cache import cache

from rest_framework import status
from rest_framework.response import Response
from django.db.models.functions import TruncDay
from datetime import timedelta
from django.utils import timezone
from .serializers import (
    GetWorkerAdminSerializer, 
    GetEmployerAdminSerializer, 
    JobAdminSerializer, 
    FinancialAdminSerializer
)

from rest_framework.pagination import PageNumberPagination

# Create your views here.


class AdminGetAllWorkers(APIView):
    permission_classes=[IsAuthenticated,IsAdminUser]

    def get(self,request):
        worker_datas = WorkerProfile.objects.select_related('user').prefetch_related('skills').all()
        serializer = GetWorkerAdminSerializer(worker_datas,many=True)
        return Response({'Message':'Successfully fetched all workers','result':serializer.data},status=status.HTTP_200_OK)
    
class AdminBlockWorker(APIView):
    permission_classes=[IsAuthenticated,IsAdminUser]
    
    def post(self,request,worker_id):
        try:
            worker = WorkerProfile.objects.get(id=worker_id)
            hustlr_user = worker.user.user
            
            hustlr_user.is_active = not hustlr_user.is_active
            hustlr_user.save()
            
            # Invalidate dashboard cache so counts update immediately
            cache.delete('admin_dashboard_stats')
            
            status_msg = "blocked" if not hustlr_user.is_active else "unblocked"
            return Response({'Message': f'Worker {status_msg} successfully', 'is_active': hustlr_user.is_active}, status=status.HTTP_200_OK)
            
        except WorkerProfile.DoesNotExist:
            return Response({'Error': 'Worker not found'}, status=status.HTTP_404_NOT_FOUND)

class AdminBlockEmployer(APIView):
    permission_classes=[IsAuthenticated,IsAdminUser]
    
    def post(self,request,employer_id):
        try:
            # Get the employer and traverse relationship to HustlrUser
            employer = EmployerProfile.objects.get(id=employer_id)
            hustlr_user = employer.user.user
            
            # Toggle the is_active status
            hustlr_user.is_active = not hustlr_user.is_active
            hustlr_user.save()
            
            # Invalidate dashboard cache so counts update immediately
            cache.delete('admin_dashboard_stats')
            
            status_msg = "blocked" if not hustlr_user.is_active else "unblocked"
            return Response({'Message': f'Employer {status_msg} successfully', 'is_active': hustlr_user.is_active}, status=status.HTTP_200_OK)
            
        except EmployerProfile.DoesNotExist:
            return Response({'Error': 'Employer not found'}, status=status.HTTP_404_NOT_FOUND)

class AdminGetAllEmployers(APIView):
    permission_classes=[IsAuthenticated,IsAdminUser]
    def get(self,request):

        employer_datas = EmployerProfile.objects.select_related('user').all()
        serializer = GetEmployerAdminSerializer(employer_datas,many=True)
        return Response({'Message':'employers datas retrieved successfully','result':serializer.data},status=status.HTTP_200_OK)



class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50

    def get_paginated_response(self, data):
        return Response({
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'Message': 'All jobs retrieved',
            'result': data
        })

class AdminGetAllJobs(APIView):
    permission_classes=[IsAuthenticated,IsAdminUser]
    def get(self, request):
        status_filter = request.query_params.get('status', None)
        jobs = JobRequest.objects.select_related('employer', 'worker').all().order_by('-created_at')
        
        if status_filter:
            if status_filter == 'in_progress':
                jobs = jobs.filter(status__in=['accepted', 'in_progress', 'starting'])
            elif status_filter == 'pending':
                jobs = jobs.filter(status='pending')
            elif status_filter == 'completed':
                jobs = jobs.filter(status='completed')
            elif status_filter == 'cancelled_or_rejected':
                 jobs = jobs.filter(status__in=['rejected', 'cancelled'])

        paginator = CustomPagination()
        paginated_jobs = paginator.paginate_queryset(jobs, request)
        serializer = JobAdminSerializer(paginated_jobs, many=True)
        return paginator.get_paginated_response(serializer.data)

class AdminGetAllFinancials(APIView):
    permission_classes=[IsAuthenticated,IsAdminUser]
    def get(self, request):
        billings = JobBilling.objects.select_related('job__employer', 'job__worker').all().order_by('-submitted_at')
        serializer = FinancialAdminSerializer(billings, many=True)
        return Response({'Message': 'All financial records retrieved', 'result': serializer.data}, status=status.HTTP_200_OK)

class AdminDashboardStats(APIView):
    permission_classes=[IsAuthenticated,IsAdminUser]
    
    def get(self, request):
        # Determine for cache keys
        cache_key = 'admin_dashboard_stats'
        data = cache.get(cache_key)
        
        if not data:
            total_workers = WorkerProfile.objects.count()
            total_employers = EmployerProfile.objects.count()
            
            # Combine active and blocked users query
            user_stats = HustlrUsers.objects.aggregate(
                total_active=Count('id', filter=Q(is_active=True)),
                total_blocked=Count('id', filter=Q(is_active=False))
            )
            
            # 2. Job Statistics (Optimized from 4 to 1 query)
            job_stats = JobRequest.objects.aggregate(
                pending=Count('id', filter=Q(status='pending')),
                active=Count('id', filter=Q(status__in=['accepted', 'in_progress', 'starting'])),
                completed=Count('id', filter=Q(status='completed')),
                cancelled_or_rejected=Count('id', filter=Q(status__in=['rejected', 'cancelled']))
            )
            
            # 3. Job Boards
            total_job_posts = JobPost.objects.count()
            
            # 4. Financial / Economy
            total_billed = JobBilling.objects.aggregate(total=Sum('total_amount'))['total'] or 0.00
            
            # 5. Timeseries for Growth Chart (Last 7 days)
            last_7_days = timezone.now() - timedelta(days=7)
            growth_query = HustlrUsers.objects.filter(date_joined__gte=last_7_days) \
                .annotate(day=TruncDay('date_joined')) \
                .values('day') \
                .annotate(count=Count('id')) \
                .order_by('day')
            
            growth_data = {
                'labels': [item['day'].strftime('%A') for item in growth_query],
                'counts': [item['count'] for item in growth_query]
            }

            data = {
                'users': {
                    'total_workers': total_workers,
                    'total_employers': total_employers,
                    'total_active': user_stats['total_active'],
                    'total_blocked': user_stats['total_blocked']
                },
                'jobs': {
                    'pending': job_stats['pending'],
                    'active': job_stats['active'],
                    'completed': job_stats['completed'],
                    'cancelled_or_rejected': job_stats['cancelled_or_rejected'],
                    'total_job_posts': total_job_posts
                },
                'financials': {
                    'total_platform_billing': float(total_billed)
                },
                'growth_stats': growth_data
            }
            
            # Cache the result for 5 minutes (300 seconds) to prevent heavy DB load
            cache.set(cache_key, data, timeout=300)
            
        return Response({'Message': 'Dashboard stats retrieved successfully', 'result': data}, status=status.HTTP_200_OK)

        