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
            # Get the top 5 job IDs
            found_job_ids = [doc.metadata.get("job_id") for doc in filtered_docs][:5]
            print(f"DEBUG: Found {len(found_job_ids)} job IDs in vector DB: {found_job_ids}", flush=True)
            
            # Querying employerapp_jobpost and joining with authapp_profile for employer info
            metadata_query = text("""
                SELECT 
                    jp.id as job_id,
                    jp.title,
                    jp.description as job_desc,
                    jp.job_image,
                    ep.company_name,
                    p.image as employer_avatar,
                    p.username as fallback_name
                FROM employerapp_jobpost jp
                JOIN employerapp_employerprofile ep ON jp.employer_id = ep.id
                JOIN authapp_profile p ON ep.user_id = p.id
                WHERE jp.id IN :ids
                """)
            
            rows = db.execute(metadata_query, {"ids": tuple(found_job_ids)}).fetchall()
            print(f"DEBUG: SQL query returned {len(rows)} job profiles for IDs {found_job_ids}", flush=True)
            
            for row in rows:
                # Construct Avatar URL (Keep existing pattern unless user wants it changed too)
                avatar_url = None
                if row.employer_avatar:
                    if row.employer_avatar.startswith('http'):
                        avatar_url = row.employer_avatar
                    else:
                        avatar_url = f"https://aiman-hustlr-media.s3.ap-south-1.amazonaws.com/{row.employer_avatar}"
                
                # Construct Cloudinary URL for Job Image
                job_img_raw = row.job_image
                project_image = None
                if job_img_raw:
                    if job_img_raw.startswith('http'):
                        project_image = job_img_raw
                    else:
                        # Keep the full path as stored in DB (including media/ if present)
                        # Cloudinary MediaCloudinaryStorage usually uses the full path as public ID
                        project_image = f"https://res.cloudinary.com/dysocs9te/image/upload/{job_img_raw}"
                
                print(f"DEBUG: Job ID {row.job_id} -> Generated URL: {project_image}", flush=True)
                
                job_metadata.append({
                    "id": row.job_id, # Sent to frontend so worker can "Apply"
                    "title": row.title,
                    "employer_name": row.company_name or row.fallback_name or "Hustlr Employer",
                    "avatar": avatar_url,
                    "project_image": project_image,
                    "description": row.job_desc[:150] + "..." if row.job_desc else "", # Snippet for card
                    "type": "Job Post"
                })
                
    except Exception as e:
        print(f"Vector search error in fetch_jobs: {e}")

    return job_metadata, final_matches