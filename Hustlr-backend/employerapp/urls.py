from django.urls import path
from .views import EmployerProfileSetupView,JobRequestView,JobRequestHandleView,JobRequestInduvidualHandleView,ChatListView, MaterialToggleView,JobPostView,\
EmployerHandleRequestView,JobPostHandleDelete,CreateRayzorpayClientOrder,RayzorpayVerifyClientOrder,EmployerPaymentHistoryView

urlpatterns = [
    path("employer-setup/", EmployerProfileSetupView.as_view(), name="employer-setup"),
    path('job-request/',JobRequestView.as_view(),name='send-job-request'),
    path('request-handle/',JobRequestHandleView.as_view(),name='request-handle'),
    path('request-handle/<int:jobRequestId>/',JobRequestInduvidualHandleView.as_view(),name='request-handle-induvidual'),
    path('chat-list/',ChatListView.as_view(),name='chat-list'),
    path('material-toggle/<int:materialId>/', MaterialToggleView.as_view(), name='material-toggle'),
    path('job-post/', JobPostView.as_view(), name='job-post'),
    path('job-post-delete/<int:post_id>/', JobPostHandleDelete.as_view(), name='job-post-delete'),
    path('job-interest-handle/', EmployerHandleRequestView.as_view(), name='list-job-interests'),
    path('job-interest-handle/<int:request_id>/', EmployerHandleRequestView.as_view(), name='actions-for-job-interest'),
    path('create-payment-client/<int:job_billing_id>/',CreateRayzorpayClientOrder.as_view(),name='create-client'),
    path('payment-verify/',RayzorpayVerifyClientOrder.as_view(),name='verify-payment'),
    path('payment-history/', EmployerPaymentHistoryView.as_view(), name='payment-history'),
]