from django.urls import path
from .views import WorkerProfileSetupView,SkillView,WorkerListView,JobInboxView,HandleJobRequestView,GetActiveJobs,GetNotificationView,JobMaterialsView,SeeJobMaterialsView

urlpatterns = [
    path("worker-setup/", WorkerProfileSetupView.as_view(), name="worker-setup"),
    path('all-workers/',WorkerListView.as_view(),name='all-workers'),
    path('skill/',SkillView.as_view(),name='skill'),
    path('job-inbox/',JobInboxView.as_view(),name='job-inbox'),
    path('job-request-handle/<int:jobRequestId>/',HandleJobRequestView.as_view(),name='job-request-handle'), 
    path('see-notification/',GetNotificationView.as_view(),name='see-notification'),
    path('active-jobs/',GetActiveJobs.as_view(),name='active-jobs'),
    path('job-materials/',JobMaterialsView.as_view(),name='job-materials'),
    path('see-job-materials/<int:job_id>/',SeeJobMaterialsView.as_view(),name='see-job-materials'),


]
