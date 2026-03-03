from django.urls import path
from .views import WorkerProfileSetupView,SkillView,WorkerListView,JobInboxView,HandleJobRequestView,GetNotificationView

urlpatterns = [
    path("worker-setup/", WorkerProfileSetupView.as_view(), name="worker-setup"),
    path('all-workers/',WorkerListView.as_view(),name='all-workers'),
    path('skill/',SkillView.as_view(),name='skill'),
    path('job-inbox/',JobInboxView.as_view(),name='job-inbox'),
    path('job-request-handle/<int:jobRequestId>/',HandleJobRequestView.as_view(),name='job-request-handle'), 
    path('get-notification/',GetNotificationView.as_view(),name='get-notification'),


]
