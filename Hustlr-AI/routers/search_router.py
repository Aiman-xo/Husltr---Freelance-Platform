from fastapi import APIRouter, Depends,Header,HTTPException
from sqlalchemy.orm import Session
from database import get_db
from services.search_service import search_workers_service

import redis

redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

router = APIRouter()

@router.get("/search")

def search_workers(query: str,user_id:int,db: Session = Depends(get_db)):
    """Search for workers by querying database explicitly and leveraging RAG context"""
    role =redis_client.get(f"user_role:{user_id}") or 'worker'
    print(f"DEBUG: Redis retrieved role '{role}' for user {user_id}", flush=True)
    return search_workers_service(query,user_id,role,db)
