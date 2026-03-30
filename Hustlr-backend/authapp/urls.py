from unicodedata import name
from django.urls import path
from .views import UserCreateView,LoginView,CookieRefreshView,GenerateOTPView,VerifyOTPView,ResetPasswordView,GoogleOAuthView,LogoutView,ProfileSetupView,UserListView,\
InternalUserInfoView,UpdateOrCreateFCMToken

urlpatterns = [
    path('register/',UserCreateView.as_view(),name='user-create'),
    path('login/',LoginView.as_view(),name = 'login'),
    path('token/refresh/',CookieRefreshView.as_view(),name = 'refresh'),
    path('reset/otp/',GenerateOTPView.as_view(),name='otp'),
    path('verify/otp/',VerifyOTPView.as_view(),name='verify'),
    path('reset/password/',ResetPasswordView.as_view(),name='reset-password'),
    path('google/auth/',GoogleOAuthView.as_view(),name='google-auth'),
    path('profile-setup/',ProfileSetupView.as_view(),name='profile-setup'),
    path('all-users/',UserListView.as_view(),name='all-users'),
    path('internal-verify/', InternalUserInfoView.as_view(), name='internal_verify'),
    path('update-fcm_token/', UpdateOrCreateFCMToken.as_view(), name='update-or-create-fcm'),
    path('logout/',LogoutView.as_view(),name='logout'),
]