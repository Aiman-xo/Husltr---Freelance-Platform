import httpx
from celery import shared_task

@shared_task(bind=True, max_retries=3)
def send_job_to_n8n(self, job_data):
    """
    Celery task to notify n8n about a new job.
    Retries up to 3 times if the connection fails.
    """
    webhook_url = "http://hustlr_n8n:5678/webhook/job-posted"
    
    try:
        response = httpx.post(webhook_url, json=job_data, timeout=5.0)
        response.raise_for_status()
        return f"Successfully notified n8n for Job ID {job_data.get('job_id')}"
        
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        # Retry the task in 60 seconds if it fails
        raise self.retry(exc=exc, countdown=60)