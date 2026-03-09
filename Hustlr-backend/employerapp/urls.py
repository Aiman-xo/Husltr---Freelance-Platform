from django.urls import path
from .views import EmployerProfileSetupView,JobRequestView,JobRequestHandleView,JobRequestInduvidualHandleView,ChatListView

urlpatterns = [
    path("employer-setup/", EmployerProfileSetupView.as_view(), name="employer-setup"),
    path('job-request/',JobRequestView.as_view(),name='send-job-request'),
    path('request-handle/',JobRequestHandleView.as_view(),name='request-handle'),
    path('request-handle/<int:jobRequestId>/',JobRequestInduvidualHandleView.as_view(),name='request-handle-induvidual'),
    path('chat-list/',ChatListView.as_view(),name='chat-list')
]