import os
import urllib.parse
from sqlalchemy import create_engine, text
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
# import services.ai_service as ai_service (Moved inside function)

def run_vector_sync():
    # 1. Database Connection (Dynamic from Env)
    RAW_USER = os.getenv('DB_USER') or os.getenv('POSTGRES_USER')
    RAW_PASS = os.getenv('DB_PASSWORD') or os.getenv('POSTGRES_PASSWORD')
    RAW_HOST = os.getenv('DB_HOST', 'aws-1-ap-south-1.pooler.supabase.com')
    RAW_PORT = os.getenv('DB_PORT', '6543')
    RAW_NAME = os.getenv('DB_NAME', 'postgres')

    if not RAW_PASS or not RAW_USER:
        print("ERROR: Database credentials not found in environment.")
        return False
        
    safe_password = urllib.parse.quote_plus(RAW_PASS)
    DB_URL = f"postgresql://{RAW_USER}:{safe_password}@{RAW_HOST}:{RAW_PORT}/{RAW_NAME}"
    
    engine = create_engine(DB_URL, pool_pre_ping=True)

    # 2. Fetch Worker Data
    worker_query = """
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
    
    # 3. Fetch Job Data
    job_query = """
        SELECT 
            jp.id as job_id,
            jp.title,
            jp.description,
            jp.city,
            COALESCE(ep.company_name, prof.username) as employer_name,
            prof.user_id as employer_user_id
        FROM employerapp_jobpost jp
        JOIN employerapp_employerprofile ep ON jp.employer_id = ep.id
        JOIN authapp_profile prof ON ep.user_id = prof.id
    """

    documents = []
    try:
        with engine.connect() as conn:
            # Workers
            worker_results = conn.execute(text(worker_query)).fetchall()
            for row in worker_results:
                name = row.username if row.username else "Worker"
                content = f"Worker: {name}. Skills: {row.skills_list if row.skills_list else 'None'}. Bio: {row.job_description}"
                documents.append(Document(
                    page_content=content,
                    metadata={"worker_id": row.real_user_id, "type": "worker"}
                ))
            
            # Jobs
            job_results = conn.execute(text(job_query)).fetchall()
            for row in job_results:
                content = f"JOB_POST: {row.title}. Posted by: {row.employer_name}. Location: {row.city}. Description: {row.description}"
                documents.append(Document(
                    page_content=content,
                    metadata={
                        "type": "job",
                        "job_id": row.job_id,
                        "employer_id": row.employer_user_id
                    }
                ))
    except Exception as e:
        print(f"Sync DB Error: {e}")
        return False

    if not documents:
        print("No documents found to sync.")
        return False

    # 4. Create Index
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        vector_db = FAISS.from_documents(documents, embeddings)
        vector_db.save_local("faiss_index")
        
        # 5. Reload the global index in ai_service
        # This is CRITICAL so the running API sees the changes
        import services.ai_service as ai_service
        new_db = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
        ai_service.vector_db = new_db
        
        print(f"Sync Complete! {len(documents)} entries indexed.")
        return True
    except Exception as e:
        print(f"FAISS Sync Error: {e}")
        return False
