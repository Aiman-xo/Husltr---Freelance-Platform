from django.urls import path
from .views import WorkerProfileSetupView,SkillView,WorkerListView

urlpatterns = [
    path("worker-setup/", WorkerProfileSetupView.as_view(), name="worker-setup"),
    path('all-workers/',WorkerListView.as_view(),name='all-workers'),
    path('skill/',SkillView.as_view(),name='skill'),
]
