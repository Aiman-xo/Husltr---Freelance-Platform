from services.ai_service import vector_db
from sqlalchemy.orm import Session
from sqlalchemy import text

def fetch_workers_for_employer(query: str, nearby_ids: list, db: Session):
    """
    Handles semantic search and SQL metadata retrieval for finding workers.
    """
    final_matches = []
    worker_metadata = []

    # Only proceed if we have nearby users to filter against
    if not nearby_ids or not vector_db:
        return worker_metadata, final_matches

    try:
        # 1. Semantic Retrieval (Top 30 matches)
        docs = vector_db.similarity_search(query, k=30)
        
        # 2. Filter matches to only those physically nearby
        filtered_docs = [
            doc for doc in docs 
            if doc.metadata.get("worker_id") in nearby_ids
        ]
        
        final_matches = [doc.page_content for doc in filtered_docs]
        
        # 3. Fetch Detailed Metadata for UI Cards
        if filtered_docs:
            # Get the top 5 worker IDs to prevent overloading the UI
            found_ids = [doc.metadata.get("worker_id") for doc in filtered_docs][:5]
            print(f"DEBUG: Found {len(found_ids)} worker IDs in vector DB: {found_ids}", flush=True)
            
            metadata_query = text("""
                SELECT 
                    wp.id as worker_profile_id, 
                    p.id as profile_id,
                    p.username, 
                    p.image as avatar, 
                    p.user_id as user_auth_id,
                    wp.job_description as bio,
                    (SELECT COUNT(*) FROM employerapp_jobrequest jr 
                     WHERE jr.worker_id = wp.id AND jr.status = 'completed') as jobs,
                    wp."base_Pay" as base_pay,
                    wp.hourly_rate
                FROM authapp_profile p
                JOIN workerapp_workerprofile wp ON p.id = wp.user_id
                WHERE p.user_id IN :ids
            """)
            
            rows = db.execute(metadata_query, {"ids": tuple(found_ids)}).fetchall()
            print(f"DEBUG: SQL query returned {len(rows)} worker profiles for IDs {found_ids}", flush=True)
            
            for row in rows:
                # Construct S3 URL if image exists
                avatar_url = None
                if row.avatar:
                    avatar_url = f"https://aiman-hustlr-media.s3.ap-south-1.amazonaws.com/{row.avatar}"
                
                worker_metadata.append({
                    "id": row.worker_profile_id, # Sent to frontend for Job Requests
                    "name": row.username if row.username else "Worker",
                    "avatar": avatar_url,
                    "bio": row.bio,
                    "rating": 5.0, # Placeholder as per your original code
                    "jobs": row.jobs,
                    "base_Pay": str(row.base_pay) if row.base_pay else "0",
                    "hourly_rate": str(row.hourly_rate) if row.hourly_rate else "0"
                })
                
    except Exception as e:
        print(f"Vector search error in fetch_workers: {e}")

    return worker_metadata, final_matches
