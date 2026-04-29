import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# Load keys
load_dotenv(dotenv_path="../Hustlr-backend/.env")
load_dotenv()

embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

try:
    vector_db = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
    
    # Try a broad search
    docs = vector_db.similarity_search("JOB_POST", k=50)
    
    jobs = [d for d in docs if d.metadata.get("type") == "job"]
    workers = [d for d in docs if d.metadata.get("type") == "worker"]
    
    print(f"TOTAL DOCS IN FAISS (top 50 for 'JOB_POST'): {len(docs)}")
    print(f"JOBS FOUND: {len(jobs)}")
    print(f"WORKERS FOUND: {len(workers)}")
    
    if jobs:
        print(f"SAMPLE JOB METADATA: {jobs[0].metadata}")
        
except Exception as e:
    print(f"ERROR: {e}")
