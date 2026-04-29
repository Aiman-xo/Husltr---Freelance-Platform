from django.db.models import Sum, Count, Q
import boto3
import os
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
from employerapp.models import JobBilling
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=JobBilling)
def update_worker_analytics(sender, instance, created, **kwargs):
    """
    Triggers whenever a JobBilling record is saved.
    Recalculates worker totals from SQL and updates DynamoDB atomically.
    """
    try:
        worker_id = instance.job.worker.id
        
        # 1. Initialize DynamoDB
        dynamodb = boto3.resource(
            'dynamodb',
            region_name=getattr(settings, "AWS_S3_REGION_NAME", os.getenv("AWS_REGION", "ap-south-1")),
            aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
            aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None)
        )
        table_name = os.getenv('ANALYTICS_TABLE_NAME', 'Hustlr_Worker_Analytics')
        table = dynamodb.Table(table_name)

        # 2. Calculate REAL totals from SQL (Only counting PAID jobs)
        # This ensures revenue only shows up after payment success
        stats = JobBilling.objects.filter(
            job__worker__id=worker_id,
            is_paid=True
        ).aggregate(
            total_rev=Sum('total_amount'),
            j_count=Count('id'),
            p_count=Count('id', filter=Q(was_penalty_applied=True))
        )


        # 3. Update the SUMMARY item (Uses put_item to overwrite and fix any previous errors)
        table.put_item(
            Item={
                'PK': f'WORKER#{worker_id}',
                'SK': 'SUMMARY',
                'total_revenue': Decimal(str(stats['total_rev'] or 0)),
                'job_count': stats['j_count'],
                'penalty_count': stats['p_count'],
                'type': 'WORKER_SUMMARY'
            }
        )

        # 4. Store/Update the individual JOB entry (For Charts)
        # We use put_item here too so it just overwrites if it already exists
        if instance.submitted_at:
            date_str = instance.submitted_at.strftime("%Y%m%d")
            table.put_item(
                Item={
                    'PK': f'WORKER#{worker_id}',
                    'SK': f'JOB#{date_str}#{instance.job.id}',
                    'total_amount': Decimal(str(instance.total_amount or 0)),
                    'labor_amount': Decimal(str(instance.labor_amount or 0)),
                    'was_penalty': instance.was_penalty_applied,
                    'timestamp': instance.submitted_at.isoformat(),
                    'type': 'BILLING_ENTRY'
                }
            )

    except Exception as e:
        logger.error(f"Failed to update DynamoDB worker analytics: {str(e)}")