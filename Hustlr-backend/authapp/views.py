from urllib.parse import unquote

import requests
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from django.db import transaction
from django.shortcuts import render
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView, Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import HustlrUsers, Profile, ResetPassword
from .serializers import (
    CreateUserSerializer,
    GenerateOTPserializer,
    LoginSerializer,
    ProfileSetupSerializer,
    ResetPasswordSerializer,
    VerifyOTPSerializer,
)
from .publisher import publish_user_details
import logging
logger = logging.getLogger(__name__)
# Create your views here.


class UserCreateView(APIView):
    @swagger_auto_schema(
        request_body=CreateUserSerializer,
        responses={
            201: openapi.Response(
                "Register Successful",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "message": openapi.Schema(type=openapi.TYPE_STRING),
                        "access_token": openapi.Schema(type=openapi.TYPE_STRING),
                        "is_new_user": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    },
                ),
            ),
            400: "Bad Request (validation error)",
            500: "Internal server error",
        },
    )
    def post(self, request):
        serializer = CreateUserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            token = RefreshToken.for_user(user)
            token["id"] = user.id
            token["email"] = user.email
            token["role"] = user.profile.active_role
            token["date_joined"] = str(user.date_joined)

            refresh_token = str(token)
            access_token = str(token.access_token)

            response = Response(
                {
                    "message": "User created successfully",
                    "access_token": access_token,
                    "is_new_user": True,
                },
                status=status.HTTP_201_CREATED,
            )
            response.set_cookie(
                key="refresh_token",
                value=refresh_token,
                httponly=True,
                secure=False,
                samesite="Lax",
                max_age=60 * 60 * 24,
                path="/",
            )
            return response
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    @swagger_auto_schema(
        request_body=LoginSerializer,
        responses={
            200: openapi.Response(
                "Login Successful",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "message": openapi.Schema(type=openapi.TYPE_STRING),
                        "access_token": openapi.Schema(type=openapi.TYPE_STRING),
                        "is_new_user": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    },
                ),
            ),
            401: "Invalid credentials",
            400: "Bad Request",
        },
    )
    def post(self, request):

        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data.get("email")
        password = serializer.validated_data.get("password")

        user = authenticate(request=request, email=email, password=password)

        if not user:
            return Response(
                {"message": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
            )

        update_last_login(None, user)

        if not user.is_active:
            return Response(
                {"message": "You are blocked by admin"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # reason for this if profile or token doesnt exist the server crashes so to handle it
        try:
            token = RefreshToken.for_user(user)
            token["id"] = user.id
            token["email"] = user.email
            token["role"] = user.profile.active_role
            token["date_joined"] = str(user.date_joined)
            refresh_token = str(token)
            access_token = str(token.access_token)
            
            try:
                print(f"DEBUG LOGIN: Triggering RabbitMQ for User {user.id} ({user.profile.active_role})", flush=True)
                publish_user_details(user.id, user.profile.active_role)
            except Exception as e:
                logger.error(f"Post-login publisher failed: {e}")

        except AttributeError:
            return Response(
                {"message": "User has no profile assigned"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            return Response(
                {"message": "Token generation failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        

        response = Response(
            {
                "message": "User logged in successfully",
                "access_token": access_token,
                "is_new_user": False,
            },
            status=status.HTTP_200_OK,
        )

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False,
            samesite="Lax",
            max_age=60 * 60 * 24,
            path="/",
        )

        return response


class LogoutView(APIView):
    @swagger_auto_schema(
        operation_description="Logs out the user by blacklisting the refresh token and clearing the cookie.",
        responses={200: "Successfully logged out", 401: "Unauthorized"},
    )
    def post(self, request):
        response = Response({"message": "logout successful"}, status=status.HTTP_200_OK)

        response.delete_cookie(
            key="refresh_token",
            samesite="None",
        )
        return response


class CookieRefreshView(APIView):
    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            return Response(
                {"error": "refresh token missing!"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)
            user_id = token["user_id"]
            user = HustlrUsers.objects.get(id=user_id)
            new_refresh = RefreshToken.for_user(user)
            new_access = new_refresh.access_token
            token.blacklist()

        except Exception as e:
            print(e)
            return Response(
                {"error": "invalid or expired token!"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        response = Response(
            {
                "message": "successfully generated tokens",
                "access_token": str(new_access),
            },
            status=status.HTTP_200_OK,
        )

        response.set_cookie(
            key="refresh_token",
            value=str(new_refresh),
            httponly=True,
            secure=False,
            samesite="Lax",
        )
        return response


class GenerateOTPView(APIView):
    def post(self, request):
        serializer = GenerateOTPserializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = serializer.save()

        return Response(
            {
                "message": "otp send successfully",
                "reset_session": session.reset_session,
            },
            status=status.HTTP_200_OK,
        )


class VerifyOTPView(APIView):
    def post(self, request):

        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp_obj = serializer.validated_data["otp_obj"]

        otp_obj.is_verified = True
        otp_obj.save()

        return Response({"message": "otp verified"}, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reset_session = serializer.validated_data["reset_session"]
        new_password = serializer.validated_data["new_password"]

        try:
            otp_obj = ResetPassword.objects.get(
                reset_session=reset_session, is_verified=True
            )
        except ResetPassword.DoesNotExist:
            return Response(
                {"error": "invalid session"}, status=status.HTTP_400_BAD_REQUEST
            )

        user = otp_obj.user
        user.set_password(new_password)
        user.save()

        otp_obj.delete()
        return Response(
            {"message": "Password changed successfully"}, status=status.HTTP_200_OK
        )


# views.py
class GoogleOAuthView(APIView):

    def post(self, request):
        raw_code = request.data.get("code")
        role = request.data.get("role")
        code = unquote(raw_code) if raw_code else None

        if not code:
            return Response({"error": "Authorization code missing"}, status=400)

        # 2. Exchange code for access token
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        }

        token_response = requests.post(token_url, data=token_data)
        token_json = token_response.json()

        if "access_token" not in token_json:
            return Response(
                {
                    "error": "Failed to obtain access token from Google",
                    "details": token_json,  # This tells us if it was 'invalid_grant'
                },
                status=400,
            )

        access_token = token_json["access_token"]

        # 3. Fetch user info using the access token
        user_info_response = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_info = user_info_response.json()

        email = user_info.get("email")

        if not email:
            return Response(
                {
                    "error": "Google did not provide an email. Check your scopes.",
                    "details": user_info,
                },
                status=400,
            )

        # 4. Database operations (User & Profile)
        try:
            with transaction.atomic():
                user, created = HustlrUsers.objects.get_or_create(email=email)
                profile, _ = Profile.objects.get_or_create(user=user)

                if created:
                    if not role:
                        # This triggers the rollback
                        raise ValueError("Role is required for registration")

                    profile.active_role = role
                    profile.save()
                else:
                    # Logic for returning users:
                    # If they don't have a role yet for some reason, assign the one from request
                    if not profile.active_role and role:
                        profile.active_role = role
                        profile.save()

                # Crucial check: if there is STILL no role, the frontend will break
                if not profile.active_role:
                    raise ValueError("User has no assigned role")

                update_last_login(None, user)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        refresh = RefreshToken.for_user(user)
        refresh["id"] = user.id
        refresh["role"] = profile.active_role
        refresh["date_joined"] = str(user.date_joined)
        refresh["email"] = user.email

        response = Response(
            {"access_token": str(refresh.access_token), "is_new_user": created},
            status=status.HTTP_200_OK,
        )

        response.set_cookie(
            key="refresh_token",
            value=str(refresh),
            httponly=True,
            secure=True,
            samesite="Lax",
        )

        return response


class ProfileSetupView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def get(self, request):
        profile = request.user.profile
        serializer = ProfileSetupSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):

        user_profile = request.user.profile  # Get the existing Profile

        # 1. Update the base Profile (Image, City, etc.)
        profile_serializer = ProfileSetupSerializer(
            user_profile, data=request.data, partial=True
        )

        if profile_serializer.is_valid():
            profile_serializer.save()
            return Response(profile_serializer.data, status=status.HTTP_200_OK)

        return Response(profile_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Fetch all profiles except the one belonging to the logged-in user
        profiles = Profile.objects.exclude(user=request.user)

        # Use your existing serializer to return the data
        # Note: many=True is required for lists
        serializer = ProfileSetupSerializer(profiles, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

class InternalUserInfoView(APIView):
    permission_classes = [IsAuthenticated] 
    def get(self, request):
        user_role = "employer" if hasattr(request.user, 'employer_profile') else "worker"
        
        return Response({
            "user_id": request.user.id,
            "role": user_role,
            "username": request.user.username
        })
    
class UpdateOrCreateFCMToken(APIView):
    permission_classes=[IsAuthenticated]
    def post(self,request):
        fcm_token = request.data.get('fcm_token')
        if not fcm_token:
            return Response({'error':'there is no fcm_token provided!'},status=status.HTTP_400_BAD_REQUEST)
        
        try:
            profile = request.user.profile
            profile.fcm_token = fcm_token
            profile.save()
            return Response({'message':'succesfully acquired the token'},status=status.HTTP_200_OK)
        
        except AttributeError:
            return Response({"message": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)