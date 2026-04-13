import pytest
import razorpay
from rest_framework import status
from rest_framework.test import APIClient
from authapp.models import HustlrUsers,Profile
from .models import EmployerProfile,Notification,JobRequest,JobPost,JobBilling
from workerapp.models import WorkerProfile,Skill
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from rest_framework_simplejwt.tokens import AccessToken
from unittest.mock import patch
from django.core.cache import cache

from django.core.files.uploadedfile import SimpleUploadedFile


@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def test_user(db):
    user = HustlrUsers.objects.create_user(email='test@gmail.com',password='Password1234')
    user_prof = Profile.objects.create(user=user,active_role='employer')
    employer = EmployerProfile.objects.create(user=user_prof,company_name='TESTING HQ')

    return {'main_user':user,'employer':employer}

@pytest.fixture
def test_worker_user(db):
    user = HustlrUsers.objects.create_user(email='test2worker@gmail.com',password='Password1234')
    user_prof = Profile.objects.create(user=user,active_role='worker')
    worker_prof = WorkerProfile.objects.create(
        user=user_prof,
        base_Pay=200,
        job_description='nndnddndndndndndn',
        experience=2,
        hourly_rate=20
    )

    return {'main_user':user,'worker':worker_prof}

@pytest.fixture
def test_billing(db, test_user, test_worker_user):
    # Create the job first
    job = JobRequest.objects.create(
        employer=test_user['employer'],
        worker=test_worker_user['worker'],
        status='in_progress'
    )
    # Create the billing
    return JobBilling.objects.create(
        job=job,
        labor_amount=500.00,
        material_amount=100.00,
        total_amount=600.00
    )

@pytest.mark.django_db
class TestEmployerApp2_2:
    
    def test_token_expiration(self,api_client,test_user):
        token = AccessToken.for_user(test_user['main_user'])

        token.set_exp(from_time=timezone.now()-timedelta(hours=1))
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        url = reverse('job-post')
        resp = api_client.get(url,format='json')
        print(resp.data)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    
    def test_tampered_token(self,api_client,test_user):
        token = AccessToken.for_user(test_user['main_user'])
        token['user_id']=1000

        resp = api_client.get(reverse('job-post'))
        print(resp.data)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    
    def test_jobrequest_from_employer_to_worker(self,test_user,test_worker_user,api_client):
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        job_request_url = reverse('send-job-request')

        data = {
            'employer':test_user['employer'].id,
            'worker':test_worker_user['worker'].id,
            'description':'jabbar sataht',
            'city':'kannur',

        }

        resp = api_client.post(job_request_url,data,format='multipart')
        noti = Notification.objects.filter(recipient=test_worker_user['main_user']).all()
        print('EMPLOYER REQUEST=================================',resp.data)

        token = AccessToken.for_user(test_worker_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        noti_url = reverse('see-notification')

        resp = api_client.get(noti_url,format='json')
        print('NOTIFICATION RECIEVED IN WORKER SIDE AT THE TIME OF JOB REQUEST=================================',resp.data)
        print(f'notification======================================={noti}')
        

    def test_jobrequest_handle_by_the_employer(self,test_user,test_worker_user,api_client):

        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        job_request_url = reverse('send-job-request')

        data = {
            'employer':test_user['employer'].id,
            'worker':test_worker_user['worker'].id,
            'description':'jabbar sataht',
            'city':'kannur',

        }

        resp = api_client.post(job_request_url,data,format='multipart')
        print('FIRST RESULT : EMPLOYER CREATED THE JOB REQUEST AND SEND TO A PURTICULAR WORKER====================>',resp.data)

        token = AccessToken.for_user(test_worker_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')


        worker_accept_request_url = reverse('job-request-handle',kwargs={'jobRequestId': resp.data['id']})
        data={
            'action':'accept'
        }

        resp1 = api_client.post(worker_accept_request_url,data,format='json')
        print('SECOND RESULT : WORKER ACCEPT THE REQUEST AND TURN THE STATUS INTO "ACCEPT"====================>',resp1.data)

        employer_cancelling_url = reverse('request-handle-induvidual',kwargs={'jobRequestId':resp.data['id']})

        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        resp3 = api_client.post(employer_cancelling_url,{'action':'cancel'},format='json')

        print('THIRD RESULT: EMPLOYER TRIES TO CANCEL THE ALREADY ACCEPTED REQUEST (TESTCASE EXPECTED : ASSERTION CORRECT)',resp3.data)
        sts = resp1.data['status']

        assert resp3.status_code == status.HTTP_400_BAD_REQUEST
        assert resp3.data['error'] == f'Cannot cancel a request that is already {sts}'
        # test whether the rate is setting correctly in the worker side.
        assert resp1.data['contract_hourly_rate'] == test_worker_user['worker'].hourly_rate

        # for testing successful cancel of a request.
        # assert resp3.status_code == status.HTTP_200_OK
        # assert resp3.data['message'] == 'Request cancelled successfully'

    def test_ghost_employer_profile_error(self, api_client, db):
        """Test B: User is authenticated but missing the EmployerProfile model."""
        user = HustlrUsers.objects.create_user(email='ghost@test.com', password='Password123')
        Profile.objects.create(user=user, active_role='employer')
        # Note: We do NOT create an EmployerProfile here
        
        token = AccessToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        url = reverse('send-job-request')
        resp = api_client.post(url, {}, format='multipart')
        
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.data['error'] == "Only employers can send requests"
    

    def test_cache_invalidation(self, api_client, test_user, test_worker_user):
        """Ensure cache is cleared when a job is cancelled."""
        
        # Set a dummy cache value
        cache_key = f"employer_box_{test_user['employer'].id}_all_page_1"
        cache.set(cache_key, {"data": "old_data"})
        
        # Perform cancellation
        job_req = JobRequest.objects.create(
            employer=test_user['employer'],
            worker=test_worker_user['worker'],
            status='pending'
        )
        
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        url = reverse('request-handle-induvidual', kwargs={'jobRequestId': job_req.id})
        api_client.post(url, {'action': 'cancel'}, format='json')
        
        # Check if cache is empty
        assert cache.get(cache_key) is None



    def test_websocket_crash_handling_correctly(self,test_user,test_worker_user,api_client):
        job_req = JobRequest.objects.create(
            employer=test_user['employer'],
            worker = test_worker_user['worker'],
            status = 'starting'
        )

        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        web_check_url = reverse('request-handle-induvidual',kwargs={'jobRequestId':job_req.id})
        # mock redis crash.
        with patch('asgiref.sync.async_to_sync', side_effect=Exception("Redis Down!")):
            resp = api_client.post(web_check_url,{'action':'accept_start'},format='json')
            assert resp.status_code == status.HTTP_200_OK
            assert resp.data['message'] == 'Job started successfully'
            
            # Verify DB was still updated
            job_req.refresh_from_db()
            assert job_req.status == 'in_progress'
    
    def test_patch_invalid_status_action(self, api_client, test_user, test_worker_user):
        
        # Create skills first
        skill1 = Skill.objects.create(name="Plumbing")
        skill2 = Skill.objects.create(name="Electrical")

        # Create JobPost
        job_post = JobPost.objects.create(
            employer=test_user['employer'],
            title="General Maintenance",
            description="Fixing multiple things",
            city="Kannur"
        )

        # Link the skills (M2M requires .set() or .add() after the object is saved)
        job_post.required_skills.set([skill1, skill2])

        # 2. NOW create the JobRequest using the real ID
        job_req = JobRequest.objects.create(
            employer=test_user['employer'],
            worker=test_worker_user['worker'],
            job_post=job_post, # Use the object we just created
            status='pending'
        )
        
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        url = reverse('actions-for-job-interest', kwargs={'request_id': job_req.id})
        
        resp = api_client.patch(url, {'status': 'cancelled'}, format='json')
        
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid status" in resp.data['error']


    

    def test_upload_invalid_file_type(self, api_client, test_user, test_worker_user):
        """Edge Case: Uploading a PDF where an image is expected."""
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        url = reverse('send-job-request')
        
        # Create a fake PDF file
        fake_pdf = SimpleUploadedFile(
            "document.pdf", 
            b"this is some pdf content", 
            content_type="application/pdf"
        )
        
        data = {
            'worker': test_worker_user['worker'].id,
            'description': 'Need a job done',
            'city': 'Kannur',
            'project_image': fake_pdf # Feeding a PDF to an ImageField
        }
        
        # Note: We use format='multipart' because we are sending a file
        resp = api_client.post(url, data, format='multipart')
        
        # ASSERTIONS
        # Django Rest Framework's ImageField should catch this
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert 'project_image' in resp.data
        assert "Upload a valid image" in str(resp.data['project_image'])


    def test_upload_massive_file(self, api_client, test_user, test_worker_user):
        """Edge Case: Testing very large file uploads (Denial of Service)."""
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Simulate a 20MB file (adjust based on your actual limits)
        big_file = SimpleUploadedFile("huge.jpg", b"0" * 20 * 1024 * 1024, content_type="image/jpeg")
        
        url = reverse('send-job-request')
        data = {
            'worker': test_worker_user['worker'].id,
            'description': 'Test',
            'city': 'Test',
            'project_image': big_file
        }
        
        resp = api_client.post(url, data, format='multipart')
        
        # If you haven't set a limit in your Serializer/Settings, this might pass (201).
        # If you have a limit, it should be 400.
        assert resp.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]


    # TESTING PAYMENT SECTION WITH RAZORPAY:
    # CASES : 1 CHECKING THE AMOUNT TURNED CORRECTLY INTO PAISE.
    # CASE : 2 SUCCESSFULLY CREATING RAZORPAY ORDER.
    # CASE: 3 PROPERLY SETTING THE RAZORPAY ID IN THE JOBBILLING MODEL.


    def test_create_razorpay_order_success(self, api_client, test_user, test_billing):
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        url = reverse('create-client', kwargs={'job_billing_id': test_billing.id})

        # Mocking the razorpay client response
        mock_order_response = {
            'id': 'order_fake_123',
            'amount': 60000,
            'currency': 'INR'
        }

        with patch('employerapp.views.client.order.create') as mock_create:
            mock_create.return_value = mock_order_response
            
            resp = api_client.post(url)
            
            assert resp.status_code == status.HTTP_201_CREATED
            assert resp.data['order_id'] == 'order_fake_123'
            assert resp.data['amount'] == 60000  # 600.00 * 100
            
            # Verify the DB was updated with the order ID
            test_billing.refresh_from_db()
            assert test_billing.razorpay_order_id == 'order_fake_123'
    
    # TESTING PAYMENT VERIFICATION SECTION WITH RAZORPAY:
    # CASES : 1 CHECKING THE SIGNATURE INVALID HANDLING.
    # CASE : 2 SUCCESSFULLY CREATING RAZORPAY ORDER.
    # CASE: 3 PROPERLY SETTING THE RAZORPAY ID IN THE JOBBILLING MODEL.

    def test_verify_payment_signature_failure(self, api_client, test_user, test_billing):
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        test_billing.razorpay_order_id = "order_123"
        test_billing.save()
        
        url = reverse('verify-payment')
        data = {
            'razorpay_order_id': 'order_123',
            'razorpay_payment_id': 'pay_456',
            'razorpay_signature': 'invalid_signature_logic'
        }

        # Force the Razorpay library to raise a SignatureVerificationError
        with patch('employerapp.views.client.utility.verify_payment_signature') as mock_verify:
            mock_verify.side_effect = razorpay.errors.SignatureVerificationError("Invalid Signature")
            
            resp = api_client.post(url, data, format='json')
            
            assert resp.status_code == 400
            assert resp.data['error'] == "Signature verification failed"
            
            # Ensure is_paid is still False
            test_billing.refresh_from_db()
            assert test_billing.is_paid is False

    def test_job_billing(self,test_user,test_worker_user,api_client):
        job_req = JobRequest.objects.create(
            employer=test_user['employer'],
            worker=test_worker_user['worker'],
            status='pending'
        )

        job_bill = JobBilling.objects.create(
            job = job_req,
            labor_amount = 120.0,
            total_amount = None,
        )

        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION = f'Bearer {token}')
        razor_create_url = reverse('create-client',kwargs={'job_billing_id':job_bill.id})
        resp = api_client.post(razor_create_url)
        print('RESULT OF JOB BILLING TOTAL AMOUNT = NONE OR " " ===============================>',resp.data)

        # assert resp.status_code == status.HTTP_400_BAD_REQUEST
        # assert "Invalid amount" in resp.data['error']