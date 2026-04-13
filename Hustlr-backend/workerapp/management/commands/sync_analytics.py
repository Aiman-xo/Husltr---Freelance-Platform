import boto3
from django.core.management.base import BaseCommand
from employerapp.models import JobBilling
from decimal import Decimal
import os

class Command(BaseCommand):
    help = 'Syncs existing JobBilling data to DynamoDB'

    def handle(self, *args, **options):
        # 1. Setup Connection
        dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        table = dynamodb.Table('Hustlr_Worker_Analytics')
        
        billings = JobBilling.objects.all()
        self.stdout.write(f"Found {billings.count()} records. Starting sync...")

        for bill in billings:
            try:
                # bill.job.worker is already the WorkerProfile instance
                worker_id = str(bill.job.worker.id)
                
                rev = Decimal(str(bill.total_amount or 0))
                labor = Decimal(str(bill.labor_amount or 0))
                date_str = bill.submitted_at.strftime("%Y%m%d")

                # A. Update the SUMMARY (Lifetime Totals)
                table.update_item(
                    Key={'PK': f'WORKER#{worker_id}', 'SK': 'SUMMARY'},
                    UpdateExpression="ADD total_revenue :r, job_count :j, penalty_count :p",
                    ExpressionAttributeValues={
                        ':r': rev,
                        ':j': 1,
                        ':p': 1 if bill.was_penalty_applied else 0
                    }
                )

                # B. Add Individual Entry (For Charts)
                table.put_item(
                    Item={
                        'PK': f'WORKER#{worker_id}',
                        'SK': f'JOB#{date_str}#{bill.job.id}',
                        'total_amount': rev,
                        'labor_amount': labor,
                        'timestamp': bill.submitted_at.isoformat(),
                        'type': 'BILLING_ENTRY',
                        'was_penalty': bill.was_penalty_applied
                    }
                )
                self.stdout.write(f"Successfully synced Bill #{bill.id} for Worker {worker_id}")
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to sync Bill {bill.id}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS('--- All historical data synced to DynamoDB! ---'))