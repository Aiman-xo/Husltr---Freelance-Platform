from django.test import TestCase
from rest_framework.test import APIClient
from authapp.models import HustlrUsers,Profile
from workerapp.models import WorkerProfile
from django.urls import reverse
import pytest


# Create your tests here.
@pytest.fixture
def test_api():
    return APIClient()

@pytest.fixture
def test_logged_user(db,test_api):

    user = HustlrUsers.objects.create_user(email='salam@gmail.com',password='salam@123')
    user_profile = Profile.objects.create(user = user,active_role='worker')
    WorkerProfile.objects.create(user=user_profile,base_Pay=200,hourly_rate = 200,experience = 2)

    # url = reverse('login')
    # data = {
    #     'email':'salam@gmail.com',
    #     'password':'salam@123'
    # }
    # resp = test_api.post(url,data,format='json')
    # print('Worker Logged : ',resp.data)
    # test_api.user = user
    # return test_api

    # this force authenticate attaches the headers with its request
    test_api.force_authenticate(user=user)
    return test_api

@pytest.mark.django_db
def test_worker_list(test_logged_user):
    url = reverse('all-workers')

    response = test_logged_user.get(url,format='json')
    print("workers Data : ",response.data)


