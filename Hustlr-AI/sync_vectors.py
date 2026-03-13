import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# Load .env (it will find your GOOGLE_API_KEY)
load_dotenv(dotenv_path="../Hustlr-backend/.env")

def sync():
    # 1. Database Connection
    DB_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@db:5432/{os.getenv('POSTGRES_DB')}"
    engine = create_engine(DB_URL)

    # 2. Fetch Worker Data (Adjusted to workerapp_workerprofile)
    query = "SELECT user_id, job_description FROM workerapp_workerprofile"
    with engine.connect() as conn:
        results = conn.execute(text(query)).fetchall()

    if not results:
        print("No workers found in database to sync.")
        return

    # 3. Prepare Documents for FAISS
    documents = []
    for row in results:
        # Create a LangChain Document with metadata
        doc = Document(
            page_content=f"Bio: {row.job_description}",
            metadata={"worker_id": row.user_id}
        )
        documents.append(doc)

    # 4. Use Gemini for Embeddings
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

    # 5. Create and Save FAISS Index
    print(f"Creating index for {len(documents)} workers...")
    vector_db = FAISS.from_documents(documents, embeddings)
    vector_db.save_local("faiss_index")
    print("Success! FAISS index saved to 'faiss_index/' folder.")

if __name__ == "__main__":
    sync()