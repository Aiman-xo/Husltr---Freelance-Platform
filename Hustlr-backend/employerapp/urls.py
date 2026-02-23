from django.urls import path
from .views import EmployerProfileSetupView

urlpatterns = [
    path("employer-setup/", EmployerProfileSetupView.as_view(), name="employer-setup"),
]
