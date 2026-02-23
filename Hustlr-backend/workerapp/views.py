from django.shortcuts import render
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .permissions import IsWorker
from .models import WorkerProfile,Skill
from .serializers import WorkerProfileReadSerializer,SkillSerializer,WorkerProfileWriteSerializer

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