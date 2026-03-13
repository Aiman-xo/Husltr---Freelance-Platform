import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1. Get credentials from environment
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
DB_NAME = os.getenv("POSTGRES_DB")
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")

# 2. Construct URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 3. Create the Engine and Session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. The "Dependency" (Used in FastAPI endpoints)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()