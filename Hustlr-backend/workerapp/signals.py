import boto3
import os
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
from employerapp.models import JobBilling

# Initialize DynamoDB using your .env variables
dynamodb = boto3.resource(
    'dynamodb',
    region_name=os.getenv('AWS_REGION', 'ap-south-1')
)
table = dynamodb.Table(os.getenv('ANALYTICS_TABLE_NAME', 'Hustlr_Worker_Analytics'))

@receiver(post_save, sender=JobBilling)
def update_worker_analytics(sender, instance, created, **kwargs):
    """
    Triggers whenever a JobBilling record is saved.
    Updates the worker's total stats and logs the individual job entry.
    """
    worker_id = instance.job.worker.id
    
    # Convert Decimal to float/int for DynamoDB (it doesn't like Python Decimals)
    revenue = float(instance.total_amount or 0)
    labor = float(instance.labor_amount or 0)
    
    # 1. Update the overall SUMMARY for the worker (Atomic Update)
    # This adds to the existing numbers so you don't have to fetch them first
    table.update_item(
        Key={
            'PK': f'WORKER#{worker_id}',
            'SK': 'SUMMARY'
        },
        UpdateExpression="ADD total_revenue :r, job_count :j, penalty_count :p",
        ExpressionAttributeValues={
            ':r': Decimal(str(revenue)),
            ':j': 1 if created else 0,
            ':p': 1 if instance.was_penalty_applied else 0
        }
    )

    # 2. Store the individual JOB entry for the Line Graph
    # We use the date in the Sort Key (SK) so we can query by date range later
    date_str = instance.submitted_at.strftime("%Y%m%d")
    table.put_item(
        Item={
            'PK': f'WORKER#{worker_id}',
            'SK': f'JOB#{date_str}#{instance.job.id}',
            'total_amount': Decimal(str(revenue)),
            'labor_amount': Decimal(str(labor)),
            'was_penalty': instance.was_penalty_applied,
            'timestamp': instance.submitted_at.isoformat(),
            'type': 'BILLING_ENTRY'
        }
    )