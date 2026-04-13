from django.urls import path
from .views import WorkerProfileSetupView,SkillView,WorkerListView,JobInboxView,HandleJobRequestView,GetActiveJobs,GetNotificationView,JobMaterialsView,SeeJobMaterialsView,GetJobPosts,\
SendingInterestedRequestView,WorkerAnalyticsView,JobRequestInduvidualWorkerHandleView,WorkerPaymentHistoryView


urlpatterns = [
    path("worker-setup/", WorkerProfileSetupView.as_view(), name="worker-setup"),
    path('all-workers/',WorkerListView.as_view(),name='all-workers'),
    path('skill/',SkillView.as_view(),name='skill'),
    path('job-inbox/',JobInboxView.as_view(),name='job-inbox'),
    path('job-request-handle/<int:jobRequestId>/',HandleJobRequestView.as_view(),name='job-request-handle'), 
    path('job-request-induvidual/<int:jobRequestId>/', JobRequestInduvidualWorkerHandleView.as_view(), name='individual-job-request-worker'),
    path('see-notification/',GetNotificationView.as_view(),name='see-notification'),
    path('active-jobs/',GetActiveJobs.as_view(),name='active-jobs'),
    path('job-materials/',JobMaterialsView.as_view(),name='job-materials'),
    path('fetch-job-posts/',GetJobPosts.as_view(),name='get-job-posts'),
    path('see-job-materials/<int:job_id>/',SeeJobMaterialsView.as_view(),name='see-job-materials'),
    path('sending-interest/<int:job_id>/',SendingInterestedRequestView.as_view(),name='sending-interest'),

    path('worker-analytics/',WorkerAnalyticsView.as_view(),name='show-worker-analytics'),
    path('worker-payment-history/', WorkerPaymentHistoryView.as_view(), name='worker-payment-history'),
]
