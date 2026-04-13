from fastapi import APIRouter, Depends,Header,HTTPException
from sqlalchemy.orm import Session
from database import get_db
from services.search_service import search_workers_service

import redis

redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

router = APIRouter()

@router.get("/search")

def search_workers(query: str, user_id: int, role: str = None, db: Session = Depends(get_db)):
    """Search for workers by querying database explicitly and leveraging RAG context"""
    normalized_role = role.lower() if role else None
    
    # Check Redis as fallback ONLY
    redis_role = redis_client.get(f"user_role:{user_id}")
    
    # PRIORITY: 
    # 1. Frontend-provided role (normalized_role)
    # 2. Redis/Sync role (redis_role)
    # 3. Default to 'worker'
    final_role = normalized_role if normalized_role else (redis_role if redis_role else 'worker')
    
    print(f"DEBUG: Final Resolved Role: '{final_role}' (Source: {'Frontend' if normalized_role else 'Redis/Default'})", flush=True)
    return search_workers_service(query, user_id, final_role, db)
