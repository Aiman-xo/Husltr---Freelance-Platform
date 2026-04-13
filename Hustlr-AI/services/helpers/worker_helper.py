from services.ai_service import vector_db
from sqlalchemy.orm import Session
from sqlalchemy import text

def fetch_jobs_for_worker(query: str, nearby_ids: list, db: Session):
    """
    Handles semantic search and SQL metadata retrieval for finding Jobs for a Worker.
    """
    final_matches = []
    job_metadata = []

    # Only proceed if we have nearby users (Employers) to filter against
    if not nearby_ids or not vector_db:
        return job_metadata, final_matches

    try:
        # 1. Semantic Retrieval (Top 30 job matches)
        # Note: Ensure your vector_db index contains Job Post descriptions!
        docs = vector_db.similarity_search(query, k=30)
        
        # 2. Filter matches to only those posted by Employers physically nearby
        filtered_docs = [
            doc for doc in docs 
            if doc.metadata.get("employer_id") in nearby_ids
        ]
        
        final_matches = [doc.page_content for doc in filtered_docs]
        
        # 3. Fetch Detailed Metadata for Job Cards
        if filtered_docs:
            # DIAGNOSTIC: Check what actually exists in the DB
            all_db_ids = db.execute(text("SELECT id FROM employerapp_jobpost LIMIT 10")).fetchall()
            print(f"DIAGNOSTIC: Current Job IDs in SQL DB: {[r[0] for r in all_db_ids]}", flush=True)

            # Get the top 5 job IDs
            found_job_ids = [doc.metadata.get("job_id") for doc in filtered_docs][:5]
            print(f"DEBUG: Vector search found job IDs: {found_job_ids}", flush=True)
            
            # Querying employerapp_jobpost with minimal joins to verify data existence
            metadata_query = text("""
                SELECT 
                    jp.id as job_id,
                    jp.title,
                    jp.description as job_desc,
                    jp.job_image,
                    jp.employer_id,
                    COALESCE(ep.company_name, p.username) as employer_name,
                    p.image as employer_avatar
                FROM employerapp_jobpost jp
                LEFT JOIN employerapp_employerprofile ep ON jp.employer_id = ep.id
                LEFT JOIN authapp_profile p ON ep.user_id = p.id
                WHERE jp.id IN :ids
                """)
            
            # Ensure ids is a tuple for SQLAlchemy IN clause
            id_tuple = tuple(found_job_ids)
            rows = db.execute(metadata_query, {"ids": id_tuple}).fetchall()
            print(f"DEBUG: SQL query returned {len(rows)} job profiles for job IDs {id_tuple}", flush=True)
            
            for row in rows:
                # Construct Avatar URL
                avatar_url = None
                if row.employer_avatar:
                    if row.employer_avatar.startswith('http'):
                        avatar_url = row.employer_avatar
                    else:
                        avatar_url = f"https://aiman-hustlr-media.s3.ap-south-1.amazonaws.com/{row.employer_avatar}"
                
                # Construct S3 URL for Job Image
                job_img_raw = row.job_image
                job_image_url = None
                if job_img_raw:
                    # If it's already a full URL (like old Cloudinary link), 
                    # we extract only the filename part to point to S3 if requested.
                    if "cloudinary.com" in str(job_img_raw):
                        filename = str(job_img_raw).split('/')[-1]
                        job_image_url = f"https://aiman-hustlr-media.s3.ap-south-1.amazonaws.com/job_posts/{filename}"
                    elif str(job_img_raw).startswith('http'):
                        job_image_url = job_img_raw
                    else:
                        job_image_url = f"https://aiman-hustlr-media.s3.ap-south-1.amazonaws.com/{job_img_raw}"
                
                print(f"DEBUG: Job ID {row.job_id} -> Successfully loaded metadata", flush=True)
                
                job_metadata.append({
                    "id": row.job_id,
                    "title": row.title,
                    "employer_name": row.employer_name or "Hustlr Employer",
                    "avatar": avatar_url,
                    "job_image": job_image_url,
                    "project_image": job_image_url, # Key name compatibility
                    "description": (row.job_desc[:150] + "...") if row.job_desc else "No description",
                    "type": "Job Post"
                })
                
    except Exception as e:
        print(f"Vector search error in fetch_jobs: {e}")

    return job_metadata, final_matches