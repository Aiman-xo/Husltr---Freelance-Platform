import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import urllib.parse

# 1. Get credentials from environment
DB_USER = os.getenv("POSTGRES_USER")
RAW_PASS = os.getenv("POSTGRES_PASSWORD")
DB_NAME = os.getenv("POSTGRES_DB")
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")

safe_password = urllib.parse.quote_plus(RAW_PASS)

# 2. Construct URL
DATABASE_URL = f"postgresql://postgres.sktvofaxkckavhwceufr:{safe_password}@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"

# 3. Create the Engine and Session
engine = create_engine(

    DATABASE_URL,
    pool_size=5,            # Maintain 5 steady connections
    max_overflow=10,        # Allow 10 extra if busy
    pool_recycle=300,       # Reset connections every 5 mins
    pool_pre_ping=True      # Check if connection is alive before using it

    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. The "Dependency" (Used in FastAPI endpoints)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()