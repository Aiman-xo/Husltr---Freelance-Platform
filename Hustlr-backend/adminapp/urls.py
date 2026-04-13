from django.urls import path
from .views import (
    AdminGetAllWorkers, 
    AdminGetAllEmployers, 
    AdminBlockWorker, 
    AdminBlockEmployer, 
    AdminDashboardStats,
    AdminGetAllJobs,
    AdminGetAllFinancials
)

urlpatterns = [
    path('get-workers/', AdminGetAllWorkers.as_view(), name='get-all-workers'),
    path('get-employers/', AdminGetAllEmployers.as_view(), name='get-all-employers'),
    path('block-worker/<int:worker_id>/', AdminBlockWorker.as_view(), name='block-worker'),
    path('block-employer/<int:employer_id>/', AdminBlockEmployer.as_view(), name='block-employer'),
    path('dashboard-stats/', AdminDashboardStats.as_view(), name='dashboard-stats'),
    path('get-jobs/', AdminGetAllJobs.as_view(), name='get-all-jobs'),
    path('get-financials/', AdminGetAllFinancials.as_view(), name='get-all-financials'),
]
