from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException
from services.ai_service import is_greeting, extract_radius, generate_ai_response
from services.helpers import employer_helper,worker_helper

def search_workers_service(query: str, user_id: int, user_role:str, db: Session):
    # 1. Check for simple greeting bypass
    if is_greeting(query):
        msg = "find workers" if user_role == "employer" else "find jobs"
        return {
            "answer": f"Hello! I am the Hustlr AI Assistant. How can I help you find {msg} today?",
            "search_radius_used": 0,
            "workers_in_range_count": 0
        }

    # 2. Get Employer Location
    loc_query = text("""
                     
        SELECT loc.latitude, loc.longitude 
        FROM locationapp_location loc
        JOIN authapp_profile prof ON loc.user_id = prof.id
        WHERE prof.user_id = :id
                     
    """)
    user_loc = db.execute(loc_query, {"id": user_id}).fetchone()
    
    if not user_loc:
        print(f"ERROR: No location found for User ID {user_id}", flush=True)
        raise HTTPException(status_code=404, detail="User Location not found.")

    user_lat, user_lng = user_loc

    # 3. Distance Extraction (Regex First, LLM Fallback)
    search_radius = extract_radius(query)

    # 4. Geographic Filtering (SQL)
    geo_query = text("""
        SELECT prof.user_id 
        FROM locationapp_location loc
        JOIN authapp_profile prof ON loc.user_id = prof.id
        WHERE (6371 * acos(cos(radians(:lat)) * cos(radians(loc.latitude)) * cos(radians(loc.longitude) - radians(:lng)) + 
            sin(radians(:lat)) * sin(radians(loc.latitude)))) <= :radius
    """)
    nearby_rows = db.execute(geo_query, {"lat": user_lat, "lng": user_lng, "radius": search_radius}).fetchall()
    nearby_ids = [row[0] for row in nearby_rows]
    print(f"---------------DEBUG---------------: Found {len(nearby_ids)} users within {search_radius}km",flush=True) # Check if SQL works

    # 5. Semantic Retrieval & Helper Routing
    # We pass nearby_ids and the database session to the helpers
    if user_role == "employer":
        # Calls the function we extracted earlier
        items_metadata, final_matches = employer_helper.fetch_workers_for_employer(query, nearby_ids, db)
        print(f"-----------------DEBUG------------------: Employer Search found {len(items_metadata)} workers",flush=True)
        item_label = "workers"
    else:
        # Calls the new job-finding function
        items_metadata, final_matches = worker_helper.fetch_jobs_for_worker(query, nearby_ids, db)
        print(f"----------------DEBUG----------------: Worker Search found {len(items_metadata)} jobs",flush=True)
        item_label = "jobs"

    # 6. AI Assistant Brain
    ai_response_content = generate_ai_response(query, search_radius, final_matches,user_role)

    return {
        "answer": ai_response_content,
        "search_radius_used": search_radius,
        "workers_in_range_count": len(items_metadata),
        item_label:items_metadata
    }
