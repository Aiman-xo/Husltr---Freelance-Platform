import pytest
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework import status
from unittest.mock import patch
from django.core.cache import cache
from rest_framework.test import APIClient
from .models import WorkerProfile,Skill
from employerapp.models import EmployerProfile, JobRequest, JobPost, JobBilling, Notification, JobMaterials
from authapp.models import HustlrUsers,Profile
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def test_user(db):
    user = HustlrUsers.objects.create_user(
        email='test3worker@gmail.com',
        password='pass@1234'
    )
    user_prof = Profile.objects.create(
        user = user,
        active_role = 'worker'
    )
    worker_prof = WorkerProfile.objects.create(
        user=user_prof,
        base_Pay=200,
        job_description='nndnddndndndndndn',
        experience=2,
        hourly_rate=20
    )
    return {'main_user':user,'worker':worker_prof}

@pytest.fixture
def test_employer_user(db):
    user = HustlrUsers.objects.create_user(email='test@gmail.com',password='Password1234')
    user_prof = Profile.objects.create(user=user,active_role='employer')
    employer = EmployerProfile.objects.create(user=user_prof,company_name='TESTING HQ')

    return {'main_user':user,'employer':employer}

@pytest.fixture(autouse=True)
def clear_cache():
    """Ensure cache is empty before every test."""
    cache.clear()
    yield
    cache.clear()

class TestWorkerAPP2_3:
    def test_employer_cannot_create_worker_profile(self, api_client, test_employer_user):
        """Test: An Employer should not be able to access worker profile setup."""
        # test_user is an employer in our fixtures
        token = AccessToken.for_user(test_employer_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        url = reverse('worker-setup') 
        resp = api_client.get(url)
        
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    
    def test_worker_profile_invalid_numbers(self, api_client, test_user):
        """Test: Ensure we can't save negative pay or experience."""
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        url = reverse('worker-setup')
        data = {
            'base_Pay': -100, # Malicious/Erroneous data.
            'experience': -5,
            'hourly_rate': 0,
            'job_description': 'I am a hacker'
        }
        
        resp = api_client.post(url, data, format='json')
        print('RESULT FOR INVALID NUMBERS ===========================>',resp.data)
        
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    
    def test_get_non_existent_worker_profile(self, api_client, test_user):
        """Test: Authenticated worker with no profile yet should get a 404."""
        # Ensure no profile exists for this worker yet
        WorkerProfile.objects.filter(user=test_user['main_user'].profile).delete()
        
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        url = reverse('worker-setup')
        resp = api_client.get(url)
        
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert resp.data['message'] == "No worker profile found"

    
    def test_get_job_posts_missing_worker_profile_edge_case(self, api_client,test_user):
        """Edge case: Authenticated user has no WorkerProfile object."""
        WorkerProfile.objects.filter(user=test_user['main_user'].profile).delete()
        
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        url = reverse('get-job-posts')
        resp = api_client.get(url)
        
        # Your view catches AttributeError and returns 400
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data['error'] == 'Worker profile not found.'


    # --- Tests for SkillView ---

    def test_skill_search_filtering(self, api_client, test_user):
        """Test: icontains search logic."""
        Skill.objects.create(name="Python")
        Skill.objects.create(name="JavaScript")
        
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        url = reverse('skill')
        # Search for 'py'
        resp = api_client.get(url, {'search': 'py'})
        
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 1
        assert resp.data[0]['name'] == "Python"

    def test_skill_no_search_limit_edge_case(self, api_client, test_user):
        """Test: Returns max 5 skills when no search query is provided."""
        for i in range(10):
            Skill.objects.create(name=f"Skill {i}")
            
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        url = reverse('skill')
        resp = api_client.get(url)
        
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 5

    
    def test_create_skill_invalid_data_edge_case(self, api_client, test_employer_user):
        """Edge case: Post with empty name or missing data."""
        token = AccessToken.for_user(test_employer_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        url = reverse('skill')
        resp = api_client.post(url, {'name': ''}) # Empty name
        
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # TESTING THE FETCHING OF JOBS FROM THE DATABASE AND ALSO CHECKING THE REDIS KEY IS SETTING SUCCESSFULLY.
    def test_get_inbox_success_db_fetch(self, api_client, test_user, test_employer_user):
        """Test: Successful fetch from DB when cache is empty."""
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Create a request initiated by employer (job_post=None)
        JobRequest.objects.create(
            employer=test_employer_user['employer'],
            worker=test_user['worker'],
            description="Direct offer from employer",
            status='pending',
            job_post=None 
        )
        
        url = reverse('job-inbox') 
        resp = api_client.get(url)
        
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 1
        assert resp.data[0]['description'] == "Direct offer from employer"
        # Verify it saved to cache
        assert cache.get(f"worker_inbox_{test_user['worker'].id}") is not None

    # TESTING WHETHER THE DATA IS TAKEN FROM REDIS CACHE OR NOT.
    def test_get_inbox_cache_hit(self, api_client, test_user):
        """Test: Data is returned from Redis directly (Cache Hit)."""
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Manually seed the cache
        cache_key = f"worker_inbox_{test_user['worker'].id}"
        mock_data = [{"id": 99, "description": "Cached Job"}]
        cache.set(cache_key, mock_data)
        
        url = reverse('job-inbox')
        resp = api_client.get(url)
        
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data == mock_data
    
    # WORKER DONT WANT TO SEE THE ACCEPT OR REJECT SECTION FOR THE JOBS HE SENDS INTEREST ON.
    def test_inbox_filters_out_worker_initiated_jobs(self, api_client, test_user, test_employer_user):
        """Test: Requests where job_post is NOT NULL should NOT appear in inbox."""
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        test_job_post = JobPost.objects.create(
            employer = test_employer_user['employer'],
            title = 'jsjsjjsjs',
            description = 'djdjdjjdjdsjdskjdksjdksjdskd',
            city = 'malalalalbarrrrrrrrrrrrrrrrrrrrrrrrrr'
        )
        
        # Worker applied to a job post (This should be hidden from worker inbox)
        JobRequest.objects.create(
            employer=test_employer_user['employer'],
            worker=test_user['worker'],
            job_post=test_job_post, 
            status='pending'
        )
        
        url = reverse('job-inbox')
        resp = api_client.get(url)
        
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 0 # Should be empty

    # TEST THE REDIS CRASH SUUCESSFULLT RETURNS DATA FROM DB INSTEAD OF CRASHING
    def test_inbox_redis_failure_fallback(self, api_client, test_user):
        """Edge Case: Test fallback to DB when Redis/Cache raises an Exception."""
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        url = reverse('job-inbox')
        
        # Mock cache.get to throw an error
        with patch('django.core.cache.cache.get', side_effect=Exception("Redis connection lost")):
            resp = api_client.get(url)
            # The view has a try/except around cache.get, so it should still succeed via DB
            assert resp.status_code == status.HTTP_200_OK
    

    # ----------------------TESTING THE WORKER JOB SECTION WHERE WORKER CAN ACCEPT,REJECT,START,FINISH THE JOBS-----------------------------

    def test_invalid_action_type(self, api_client, test_user):
        """Edge Case: Sending an action not in the allowed list."""
        url = reverse('job-request-handle', kwargs={'jobRequestId': 1})
        api_client.force_authenticate(user=test_user['main_user'])
        
        resp = api_client.post(url, {'action': 'delete_everything'})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid action" in resp.data['error']
    
    def test_worker_security_boundary(self, api_client, test_user, test_employer_user):
        """Edge Case: Worker A trying to 'accept' a job assigned to Worker B."""
        # Create job for Worker A
        job_req = JobRequest.objects.create(
            employer=test_employer_user['employer'],
            worker=test_user['worker'], # Assigned to test_user
            status='pending'
        )
        
        # Authenticate as a DIFFERENT user (Worker B)
        other_user = HustlrUsers.objects.create_user(email='other@test.com', password='p')
        api_client.force_authenticate(user=other_user)
        
        url = reverse('job-request-handle', kwargs={'jobRequestId': job_req.id})
        resp = api_client.post(url, {'action': 'accept'})
        
        # Should return 404 because the queryset filters by request.user
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    # -----------------------The "Billing & Penalty" Tests-------------------------------------

    def test_billing_crash_null_start_time(self, api_client, test_user, test_employer_user):
        """
        CRASH TEST: If status is 'in_progress' but 'start_time' is NULL.
        Your view does: duration = job_req.end_time - job_req.start_time
        This WILL throw a TypeError if not handled.
        """
        job_req = JobRequest.objects.create(
            employer=test_employer_user['employer'],
            worker=test_user['worker'],
            status='in_progress',
            start_time=None # The bomb
        )
        api_client.force_authenticate(user=test_user['main_user'])
        url = reverse('job-request-handle', kwargs={'jobRequestId': job_req.id})
        
        resp = api_client.post(url, {'action': 'finish'})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    
    def test_penalty_calculation_accuracy(self,test_user,test_employer_user,api_client):
        job_req = JobRequest.objects.create(
            employer=test_employer_user['employer'],
            worker=test_user['worker'],
            status='in_progress',
            start_time=timezone.now() - timedelta(hours=2),
            estimated_hours=1.0, 
            contract_hourly_rate=100
        )

        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION = f'Bearer {token}')

        url = reverse('job-request-handle',kwargs={'jobRequestId':job_req.id})

        api_client.post(url,{'action':'finish'})
        billing = JobBilling.objects.get(job=job_req)

        
        # ***** In check// Expected: 2 hours * 100 = 200. Penalty = 200 * 0.80 = 180. by appliying 20% penalty*****. 
        # so the penalty applied will be the 1 hour pay which is basePay = 200 plus the extra time he worked
        # ie extra 1 hour so final amount = 200 + 80.  
        assert billing.labor_amount  == Decimal('280.00')
        assert billing.was_penalty_applied == True
    

    def test_1_hour_work_and_morethan_that(self,test_employer_user,test_user,api_client):
        job_req = JobRequest.objects.create(
            employer = test_employer_user['employer'],
            worker = test_user['worker'],
            status = 'in_progress',
            # sets time to 1.15 minutes ie work completed within 1 hour 15 mins.
            start_time=timezone.now() - timedelta(minutes=75),
            estimated_hours=2.0,
            contract_hourly_rate=100
        )
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION = f'Bearer {token}')

        url = reverse('job-request-handle',kwargs={'jobRequestId':job_req.id})
        api_client.post(url,{'action':'finish'})
        billing = JobBilling.objects.get(job=job_req)
        assert billing.labor_amount == Decimal('225.00')

    
    @patch('channels.layers.get_channel_layer')
    def test_websocket_failure_does_not_stop_db_save(self, mock_layer, api_client, test_user, test_employer_user):
        """Edge Case: If Redis/Channels is down, the job should still be accepted in DB."""
        mock_layer.side_effect = Exception("Redis Connection Refused")
        
        job_req = JobRequest.objects.create(
            employer=test_employer_user['employer'],
            worker=test_user['worker'],
            status='pending'
        )
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        url = reverse('job-request-handle', kwargs={'jobRequestId': job_req.id})
        resp = api_client.post(url, {'action': 'accept'})
        
        assert resp.status_code == status.HTTP_200_OK
        job_req.refresh_from_db()
        assert job_req.status == 'accepted' # The view caught the error and finished the save.


    def test_reject_job(self, api_client, test_user, test_employer_user):
        """Test: Worker rejecting a job request."""
        job_req = JobRequest.objects.create(
            employer=test_employer_user['employer'],
            worker=test_user['worker'],
            status='pending'
        )
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        url = reverse('job-request-handle', kwargs={'jobRequestId': job_req.id})
        
        resp = api_client.post(url, {'action': 'reject'})
        assert resp.status_code == status.HTTP_200_OK
        job_req.refresh_from_db()
        assert job_req.status == 'rejected'

    def test_start_job_requires_accepted(self, api_client, test_user, test_employer_user):
        """Test: Worker can only start a job that is 'accepted'."""
        job_req = JobRequest.objects.create(
            employer=test_employer_user['employer'],
            worker=test_user['worker'],
            status='pending' # Not accepted yet
        )
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        url = reverse('job-request-handle', kwargs={'jobRequestId': job_req.id})
        
        # Should fail as status is pending
        resp = api_client.post(url, {'action': 'start'})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

        job_req.status = 'accepted'
        job_req.save()
        resp = api_client.post(url, {'action': 'start'})
        assert resp.status_code == status.HTTP_200_OK
        job_req.refresh_from_db()
        assert job_req.status == 'starting'

    def test_update_job_estimate(self, api_client, test_user,test_employer_user):
        """Test: Worker updating estimated hours for an accepted job."""
        job_req = JobRequest.objects.create(
            employer=test_employer_user['employer'],
            worker=test_user['worker'],
            status='accepted'
        )
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        url = reverse('individual-job-request-worker', kwargs={'jobRequestId': job_req.id})
        
        resp = api_client.patch(url, {'estimated_hours': 5.5})
        assert resp.status_code == status.HTTP_200_OK
        job_req.refresh_from_db()
        assert job_req.estimated_hours == 5.5

    def test_get_job_posts_with_interest_flag(self, api_client, test_user, test_employer_user):
        """Test: Job posts list correctly shows 'already_interested' flag."""
        job_post = JobPost.objects.create(
            employer=test_employer_user['employer'],
            title="Test Job",
            description="Details",
            city="London"
        )
        
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        url = reverse('get-job-posts')
        
        # Initial check
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data[0]['already_interested'] == False
        
        # Create interest
        JobRequest.objects.create(
            job_post=job_post,
            worker=test_user['worker'],
            employer=test_employer_user['employer'],
            status='pending'
        )
        
        resp = api_client.get(url)
        assert resp.data[0]['already_interested'] == True

    def test_sending_interest_logic(self, api_client, test_user, test_employer_user):
        """Test: Success, duplicate prevention, and rate locking for interest requests."""
        job_post = JobPost.objects.create(
            employer=test_employer_user['employer'],
            title="Dev Job",
            description="Coding",
            city="London"
        )
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        url = reverse('sending-interest', kwargs={'job_id': job_post.id})
        
        # Success
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_201_CREATED
        
        # Rate lock check
        job_req = JobRequest.objects.get(job_post=job_post, worker=test_user['worker'])
        assert job_req.contract_hourly_rate == test_user['worker'].hourly_rate
        
        # Duplicate prevention
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "interest reuqest for this post once" in resp.data['error']

    def test_worker_list_search_and_pagination(self, api_client, test_user):
        """Test: Worker list filtering and pagination."""
        # Create a second worker
        user2 = HustlrUsers.objects.create_user(email='worker2@gmail.com', password='p')
        prof2 = Profile.objects.create(user=user2, active_role='worker')
        WorkerProfile.objects.create(
            user=prof2,
            base_Pay=200,
            job_description='Expert Python developer',
            experience=2,
            hourly_rate=20
        )
        
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        url = reverse('all-workers')
        
        # Search Python
        resp = api_client.get(url, {'search': 'Python'})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['count'] == 1
        assert "Expert Python" in resp.data['results'][0]['job_description']

    def test_notifications_fetch_and_mark_read(self, api_client, test_user):
        """Test: Fetching notifications and marking them as read."""
        Notification.objects.create(
            recipient=test_user['main_user'],
            title="Hello",
            message="World",
            is_read=False
        )
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        url = reverse('see-notification')
        
        # Fetch
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['unread_count'] == 1
        
        # Mark Read
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_200_OK
        assert Notification.objects.filter(recipient=test_user['main_user'], is_read=False).count() == 0

    def test_job_materials_and_notes(self, api_client, test_user, test_employer_user):
        """Test: Uploading and viewing job materials (notes)."""
        job_req = JobRequest.objects.create(
            employer=test_employer_user['employer'],
            worker=test_user['worker']
        )
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        url_upload = reverse('job-materials')
        
        data = [
            {'job': job_req.id, 'item_description': 'Note 1'},
            {'job': job_req.id, 'item_description': 'Note 2'}
        ]
        
        # Upload
        resp = api_client.post(url_upload, data, format='json')
        print('DEBUG=================================================================>1',resp.data)
        assert resp.status_code == status.HTTP_200_OK
        
        # View
        url_view = reverse('see-job-materials', kwargs={'job_id': job_req.id})
        resp = api_client.get(url_view)
        print('DEBUG=================================================================>2',resp.data)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 2

    def test_worker_payment_history(self, api_client, test_user, test_employer_user):
        """Test: Only paid billings appear in payment history."""
        job_req = JobRequest.objects.create(
            employer=test_employer_user['employer'],
            worker=test_user['worker']
        )
        JobBilling.objects.create(job=job_req, labor_amount=100, is_paid=True, paid_at=timezone.now())
        
        # Create an unpaid one
        job_req2 = JobRequest.objects.create(employer=test_employer_user['employer'], worker=test_user['worker'])
        JobBilling.objects.create(job=job_req2, labor_amount=200, is_paid=False)
        
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        url = reverse('worker-payment-history')
        resp = api_client.get(url)
        
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 1
        assert resp.data[0]['labor_amount'] == '100.00'

    def test_worker_analytics_mocked(self, api_client, test_user):
        """Test: Worker analytics endpoint with DynamoDB mocking."""
        token = AccessToken.for_user(test_user['main_user'])
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        url = reverse('show-worker-analytics')
        
        with patch('boto3.resource') as mock_boto:
            # Mock table.get_item and table.query
            mock_table = mock_boto.return_value.Table.return_value
            mock_table.get_item.return_value = {
                'Item': {'total_revenue': 500, 'job_count': 5, 'penalty_count': 0}
            }
            mock_table.query.return_value = {
                'Items': [
                    {'timestamp': '2024-01-01T10:00:00', 'total_amount': 100, 'labor_amount': 80},
                    {'timestamp': '2024-01-02T10:00:00', 'total_amount': 200, 'labor_amount': 160}
                ]
            }
            
            resp = api_client.get(url)
            assert resp.status_code == status.HTTP_200_OK
            assert resp.data['summary']['total_revenue'] == 500
            assert len(resp.data['chart_data']['revenue_points']) == 2