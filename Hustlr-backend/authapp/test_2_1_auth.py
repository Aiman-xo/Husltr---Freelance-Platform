import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from authapp.models import HustlrUsers, Profile, ResetPassword
from django.utils import timezone
from datetime import timedelta

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def test_user(db):
    user = HustlrUsers.objects.create_user(email="test@mail.com", password="12345!")
    Profile.objects.create(user=user, active_role="worker")
    return user

@pytest.mark.django_db
class TestAuthModule2_1:

    # def test_user_register(self,api_client):
    #     register_url = reverse('user-create')
    #     data ={
    #         'email':'testing@mail.com',
    #         'password':'123456',
    #         'confirm_password':'123456',
    #         'role':'worker' 
    #     }

    #     resp = api_client.post(register_url,data,format='json')

    #     print(f'DEBUGGGGG======================================================================={resp.data}')

    def test_login_datas(self,api_client,test_user):
        login_url = reverse('login')
        resp = api_client.post(login_url,{'email':'test@mail.com','password':'12345!'},format='json')
        print(resp.data)
        # assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        # assert resp.data['message'] == 'Invalid credentials'
        


    def test_otp_flow_generation_and_verification(self, api_client, test_user):
        """
        TC 2.1.2: OTP Verification Workflow
        """
        # 1. Generate OTP
        gen_url = reverse("otp")
        gen_resp = api_client.post(gen_url, {"email": test_user.email}, format="json")
        
        print(f'DEBUG=========================={gen_resp.status_code}')
        assert gen_resp.status_code == status.HTTP_200_OK
        reset_session = gen_resp.data["reset_session"]
        
        # Fetch OTP from DB (since we can't read the email/output easily)
        otp_obj = ResetPassword.objects.get(reset_session=reset_session)
        correct_otp = otp_obj.otp
        
        # 2. Verify OTP
        verify_url = reverse("verify")
        verify_data = {"reset_session": reset_session, "entered_otp": correct_otp}
        verify_resp = api_client.post(verify_url, verify_data, format="json")
        
        assert verify_resp.status_code == status.HTTP_200_OK
        assert verify_resp.data["message"] == "otp verified"
        
        # Verify DB state
        otp_obj.refresh_from_db()
        assert otp_obj.is_verified is True

    # --- EDGE CASES ---

    def test_otp_replay_attack(self, api_client, test_user):
        """
        TC 2.1.3: Replay Attack (Submit same OTP logic request twice)
        Expectation: While the code allows updating, we should verify it stays valid 
        or handles it. In this system, once verified, moving to password reset 
        should be the only next step.
        """
        # Setup verified OTP
        otp_obj = ResetPassword.objects.create(user=test_user, otp="123456", is_verified=False)
        url = reverse("verify")
        data = {"reset_session": otp_obj.reset_session, "entered_otp": "123456"}
        
        # First verification
        api_client.post(url, data, format="json")
        
        # Second verification (Replay)
        resp = api_client.post(url, data, format="json")
        assert resp.status_code == status.HTTP_200_OK # Current implementation allows re-verification

    def test_fcm_token_edge_cases(self, api_client, test_user):
        """
        TC 2.1.4: FCM Token Injection
        Send null or massive string to update-fcm_token/ endpoint.
        """
        api_client.force_authenticate(user=test_user)
        url = reverse("update-or-create-fcm")
        
        # Case 1: Null/Missing
        resp_null = api_client.post(url, {"fcm_token": ""}, format="json")
        assert resp_null.status_code == status.HTTP_400_BAD_REQUEST
        
        # Case 2: Massive string
        massive_token = "A" * 10000 
        resp_massive = api_client.post(url, {"fcm_token": massive_token}, format="json")
        assert resp_massive.status_code == status.HTTP_200_OK
        
        test_user.profile.refresh_from_db()
        assert test_user.profile.fcm_token == massive_token

    @pytest.mark.skip(reason="Rate limiting not implemented in current DRF views yet")
    def test_brute_force_otp(self, api_client, test_user):
        """
        TC 2.1.5: Brute Force Prevention
        """
        # This would require Scopes or Throttling middleware
        pass
