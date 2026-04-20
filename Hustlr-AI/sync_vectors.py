import os
import urllib.parse
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# Load .env (it will find your POSTGRES_USER, etc. from the backend)
load_dotenv(dotenv_path="../Hustlr-backend/.env")
# Secondary load for local service-specific keys
load_dotenv()

RAW_PASS=os.getenv('POSTGRES_PASSWORD')
safe_password = urllib.parse.quote_plus(RAW_PASS)

def sync():
    # 1. Database Connection
    DB_URL = f"postgresql://postgres.sktvofaxkckavhwceufr:{safe_password}@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"
    engine = create_engine(

        DB_URL,
        pool_size=5,             # Maintain 5 steady connections
        max_overflow=10,        # Allow 10 extra if busy
        pool_recycle=300,       # Reset connections every 5 mins
        pool_pre_ping=True      # Check if connection is alive before using it

    )

    # 2. Fetch Worker Data (Connecting Profile -> WorkerProfile)
    query = """
        SELECT 
            p.user_id as real_user_id,
            p.username, 
            wp.job_description,
            string_agg(s.name, ', ') as skills_list
        FROM authapp_profile p
        JOIN workerapp_workerprofile wp ON p.id = wp.user_id
        LEFT JOIN workerapp_workerprofile_skills wps ON wp.id = wps.workerprofile_id
        LEFT JOIN workerapp_skill s ON wps.skill_id = s.id
        GROUP BY p.user_id, p.username, wp.job_description
    """
    with engine.connect() as conn:
        results = conn.execute(text(query)).fetchall()

    if not results:
        print("No workers found in database to sync.")
        return

    # 3. Prepare Documents for FAISS
    documents = []
    for row in results:
        # Use profile_id for metadata to match search_service.py
        name = row.username if row.username else "Worker"
        content = f"Worker: {name}. Skills: {row.skills_list if row.skills_list else 'None'}. Bio: {row.job_description}"
        
        doc = Document(
            page_content=content,
            metadata={"worker_id": row.real_user_id,"type": "worker",}
        )
        documents.append(doc)
    
    job_query = """
        SELECT 
            jp.id as job_id,
            jp.title,
            jp.description,
            jp.city,
            COALESCE(ep.company_name, prof.username) as employer_name,
            prof.user_id as employer_user_id  -- <--- FETCH REAL USER ID
        FROM employerapp_jobpost jp
        JOIN employerapp_employerprofile ep ON jp.employer_id = ep.id
        JOIN authapp_profile prof ON ep.user_id = prof.id
    """
    
    with engine.connect() as conn:
        job_results = conn.execute(text(job_query)).fetchall()

    for row in job_results:
        content = f"JOB_POST: {row.title}. Posted by: {row.employer_name}. Location: {row.city}. Description: {row.description}"
        
        doc = Document(
            page_content=content,
            metadata={
                "type": "job",         # Identifies this doc as a job
                "job_id": row.job_id,
                "employer_id": row.employer_user_id # The employer's user ID for geo-filtering
            }
        )
        documents.append(doc)

    if not documents:
        print("No data found in database to sync.")
        return

    # 4. Use Gemini for Embeddings
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

    # 5. Create and Save FAISS Index
    print(f"Creating index for {len(documents)} workers... and jobs....")
    vector_db = FAISS.from_documents(documents, embeddings)
    vector_db.save_local("faiss_index")
    print("Success! FAISS index saved to 'faiss_index/' folder.")

if __name__ == "__main__":
    sync()