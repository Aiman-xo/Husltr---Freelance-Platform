import requests
import os
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from employerapp.models import JobPost

class Command(BaseCommand):
    help = 'Force Migration: Specifically targets Cloudinary URLs'

    def handle(self, *args, **options):
            # Your Cloudinary Base URL
            CLOUD_NAME = "dysocs9te"
            CLOUDINARY_BASE = f"https://res.cloudinary.com/{CLOUD_NAME}/image/upload/"

            configs = [
                {'model': JobPost, 'field': 'job_image'},
                # Add other models here if needed
            ]

            for config in configs:
                model = config['model']
                field_name = config['field']
                
                # Get all records that have an image
                all_objs = model.objects.exclude(**{field_name: ""}).exclude(**{f"{field_name}__isnull": True})
                self.stdout.write(f"\n--- Processing {all_objs.count()} records in {model.__name__} ---")

                migration_count = 0

                for obj in all_objs:
                    image_field = getattr(obj, field_name)
                    # Use .name to get the 'raw' path stored in the DB (e.g., 'media/job_posts/filename.jpg')
                    raw_path = image_field.name 
                    
                    # If the raw path starts with 'http' or 'https', it might already be a full URL.
                    # Usually, it's just the path. We want to check if it's NOT an S3 path.
                    if "amazonaws.com" not in raw_path:
                        # Construct the direct Cloudinary URL
                        # We remove 'media/' from the start if it exists, as Cloudinary usually prefixes it differently
                        # or it might already be part of your upload_to path.
                        download_url = f"{CLOUDINARY_BASE}{raw_path}"
                        
                        filename = os.path.basename(raw_path.split('?')[0])
                        self.stdout.write(self.style.WARNING(f"ID {obj.id}: Attempting to download from Cloudinary..."))
                        self.stdout.write(f"  URL: {download_url}")

                        try:
                            resp = requests.get(download_url, timeout=20)
                            if resp.status_code == 200:
                                # This saves to S3 and updates the DB record
                                image_field.save(filename, ContentFile(resp.content), save=True)
                                self.stdout.write(self.style.SUCCESS(f"  -> SUCCESS: Migrated {filename} to S3"))
                                migration_count += 1
                            else:
                                self.stdout.write(self.style.ERROR(f"  -> FAIL: Cloudinary returned {resp.status_code}"))
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"  -> ERROR: {str(e)}"))
                    else:
                        self.stdout.write(self.style.NOTICE(f"ID {obj.id}: Already on S3. Skipping."))

                self.stdout.write(self.style.SUCCESS(f"Finished {model.__name__}: {migration_count} migrated."))