import boto3
from django.core.management.base import BaseCommand
from employerapp.models import JobBilling
from authapp.models import Profile
from decimal import Decimal
import os
from django.db.models import Sum, Count, Q
from django.conf import settings

class Command(BaseCommand):
    help = 'Syncs existing JobBilling data to DynamoDB with correct totals'

    def handle(self, *args, **options):
        # 1. Setup Connection
        dynamodb = boto3.resource(
            'dynamodb', 
            region_name=getattr(settings, "AWS_S3_REGION_NAME", os.getenv("AWS_REGION", "ap-south-1")),
            aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
            aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None)
        )
        table_name = os.getenv('ANALYTICS_TABLE_NAME', 'Hustlr_Worker_Analytics')
        table = dynamodb.Table(table_name)
        
        # 2. Get all workers who have jobs
        from workerapp.models import WorkerProfile
        workers = WorkerProfile.objects.all()
        self.stdout.write(f"Syncing analytics for {workers.count()} workers...")

        for worker in workers:
            try:
                worker_id = str(worker.id)
                
                # A. Aggregate ONLY PAID stats for this worker from SQL
                stats = JobBilling.objects.filter(
                    job__worker=worker,
                    is_paid=True
                ).aggregate(
                    total_rev=Sum('total_amount'),
                    j_count=Count('id'),
                    p_count=Count('id', filter=Q(was_penalty_applied=True))
                )


                if stats['j_count'] == 0:
                    continue

                # B. Reset the SUMMARY in DynamoDB (Fixing duplicates)
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

                # C. Sync all individual job entries
                billings = JobBilling.objects.filter(job__worker=worker)
                for bill in billings:
                    if not bill.submitted_at: continue
                    date_str = bill.submitted_at.strftime("%Y%m%d")
                    table.put_item(
                        Item={
                            'PK': f'WORKER#{worker_id}',
                            'SK': f'JOB#{date_str}#{bill.job.id}',
                            'total_amount': Decimal(str(bill.total_amount or 0)),
                            'labor_amount': Decimal(str(bill.labor_amount or 0)),
                            'timestamp': bill.submitted_at.isoformat(),
                            'type': 'BILLING_ENTRY',
                            'was_penalty': bill.was_penalty_applied
                        }
                    )
                self.stdout.write(f"Cleaned and Synced stats for Worker {worker_id}")
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to sync Worker {worker.id}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS('--- All analytics reset and synced to DynamoDB! ---'))