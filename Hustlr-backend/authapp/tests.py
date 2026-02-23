from django.test import TestCase
import pytest

from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from .models import HustlrUsers
from .models import Profile
from .tasks import send_come_back_email
from rest_framework.test import APIClient



# basic unit testing : uses class based testing and also uses Testcase,TestAPICase etc..
class TestUserModel(TestCase):
    def test_last_login(self):
        user = HustlrUsers.objects.create(email = "jabbar@gmail.com",password = "jabs@123")
        print(user.is_active)


class TestUserLogin(TestCase):
    def setUp(self):
        self.email = 'jabbar@gmail.com'
        self.password = "jabs@123"
        self.user = HustlrUsers.objects.create_user(email = self.email,password = self.password)
        Profile.objects.create(user = self.user)

    def test_login(self):
        url = reverse('login')
        data = {
            "email":self.email,
            "password":self.password
        }

        resp = self.client.post(url,data,content_type='application/json')
        self.user.refresh_from_db()
        print(resp.data)
        print(self.user.last_login)
        self.assertTrue(self.user.last_login < timezone.now())
    
    def test_refresh_rotation(self):
        # 1. Login to get the initial cookie
        login_url = reverse('login')
        login_data = {"email": self.email, "password": self.password}
        login_resp = self.client.post(login_url, login_data, content_type='application/json')
        
        # 2. Capture the FIRST refresh token
        first_cookie = self.client.cookies.get('refresh_token').value
        self.assertTrue(first_cookie, "Should have a refresh token after login")

        # 3. Now call the refresh endpoint
        refresh_url = reverse('refresh')
        refresh_resp = self.client.post(refresh_url, content_type='application/json')

        # 4. Capture the SECOND (new) refresh token
        second_cookie = self.client.cookies.get('refresh_token').value

        # 5. Assertions
        self.assertEqual(refresh_resp.status_code, 200)
        # Check that the token actually CHANGED (Token Rotation)
        self.assertNotEqual(first_cookie, second_cookie)
        


# Create your tests here.
# unittest using pytest which is the modern version uses function based tests.

@pytest.fixture
def test_api():
    return APIClient()
@pytest.mark.django_db
def test_registration_and_response(test_api):
    url = reverse('user-create')
    data={
        "email":"jabbar@gmail.com",
        "password":"jabs@123",
        "confirm_password":"jabs@123",
        "role":"worker"
    }

    resp = test_api.post(url,data,format='json')
    print(resp.data)
    # If this fails, Pytest will print the status code AND the resp.data in the terminal
    assert resp.status_code == 201, f"Expected 201 but got {resp.status_code}. Errors: {resp.data}"
    assert "access_token" in resp.data
    assert resp.data.get("is_new_user") == True
    assert 'refresh_token' in resp.cookies
    assert resp.cookies['refresh_token']['httponly'] is True

    assert HustlrUsers.objects.filter(email="jabbar@gmail.com").exists()


@pytest.mark.django_db
def test_login_and_response(test_api):
    user = HustlrUsers.objects.create_user(
        email="jabbar@gmail.com", 
        password="jabs@123"
    )

    Profile.objects.create(user=user)


    url = reverse('login')

    data={
        "email":"jabbar@gmail.com",
        "password":"jabs@123"
    }

    resp = test_api.post(url,data,format='json')

    print(resp.data)

    user.refresh_from_db()
    print(user.last_login)
    print(timezone.now())
    # assert resp.status_code == 200
    assert resp.data.get('message') == "User logged in successfully"
    assert 'access_token' in resp.data
    assert resp.data.get('is_new_user') == False
    now = timezone.now()
    # Check if the login happened within the last 2 seconds
    assert (now - user.last_login).total_seconds() < 2

# create a alreadyy logged in user and can use in all the test cases from here
@pytest.fixture
def test_authentication(db,test_api):
    user = HustlrUsers.objects.create_user(
    email="jabbar@gmail.com", 
    password="jabs@123"
    )

    Profile.objects.create(user=user)
    url = reverse('login')
    data={
    "email":"jabbar@gmail.com",
    "password":"jabs@123"
    }

    test_api.post(url,data,format='json')

    test_api.user = user
    return test_api

# testing the refresh is working
@pytest.mark.django_db
def test_cookie_refresh(test_authentication):

    old_token = test_authentication.cookies['refresh_token']
    url2 = reverse('refresh')
    resp = test_authentication.post(url2)
    print(resp.data)

    new_token = resp.cookies['refresh_token']
    assert old_token != new_token


# creates a logged in user and also send the authentication credentialis in every request for that we use : force_authenticate()
@pytest.fixture
def test_authentication2(db, test_api):
    user = HustlrUsers.objects.create_user(
        email="jabbar@gmail.com", 
        password="jabs@123"
    )

    Profile.objects.get_or_create(user=user)
    
    # 1. We still do the login post so the REFRESH cookies are set
    url = reverse('login')
    login_data = {"email": "jabbar@gmail.com", "password": "jabs@123"}
    test_api.post(url, login_data, format='json')

    # 2. MAGIC LINE: This tells DRF "For every request from now on, this is the user"
    # This fixes the "credentials not provided" error for your Profile view
    test_api.force_authenticate(user=user)

    test_api.user = user
    return test_api

import io
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile

@pytest.mark.django_db
def test_profile_setup(test_authentication2):
    url = reverse('profile-setup')

    file = io.BytesIO()
    image = Image.new('RGBA',size=(100,100),color=(255,0,0,0))
    image.save(file,'png')
    file.seek(0)

    # 2. Wrap it so Django thinks it's an uploaded file
    avatar = SimpleUploadedFile('avatar.png', file.read(), content_type='image/png')

    data ={
        "image":avatar,
        "city":"malabar",
        "phone_number":"1234567890",
        "username":"jabbus12"
    }

    resp = test_authentication2.post(url,data,format='multipart')
    print(resp.data)


