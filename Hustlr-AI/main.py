import os
import re
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate

app = FastAPI(root_path="/ai")

# 1. Initialize Gemini Models
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
# Using Gemini 1.5 Flash - it's fast and has a great free tier
llm = ChatGoogleGenerativeAI(model="gemini-flash-latest")

# 2. Global FAISS Loading (Saves significant time per request)
try:
    vector_db = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
    print("FAISS index loaded successfully.")
except Exception as e:
    print(f"CRITICAL: Failed to load FAISS index: {e}")
    vector_db = None

def get_text_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content])
    return str(content)

def extract_radius(query):
    """Try to extract radius using regex to avoid an extra LLM call."""
    # Matches patterns like "5km", "10 km", "within 20 kilometers"
    matches = re.findall(r"(\d+)\s*(?:km|kilometer|km\b)", query.lower())
    if matches:
        return int(matches[0])
    return None

@app.get("/search")
def search_workers(query: str, employer_id: int, db: Session = Depends(get_db)):
    # --- STEP 1: Get Employer Location ---
    loc_query = text("SELECT latitude, longitude FROM locationapp_location WHERE user_id = :id")
    employer_loc = db.execute(loc_query, {"id": employer_id}).fetchone()
    
    if not employer_loc:
        raise HTTPException(status_code=404, detail="Location not found for this employer.")

    emp_lat, emp_lng = employer_loc

    # --- STEP 2: Distance Extraction (Regex First, LLM Fallback) ---
    search_radius = extract_radius(query)
    
    if search_radius is None:
        try:
            dist_prompt = f"Extract only the search radius in km from this query: '{query}'. If no distance or 'nearby' is mentioned, return 10. Return ONLY the number."
            radius_raw = llm.invoke(dist_prompt).content
            radius_response = get_text_content(radius_raw).strip()
            search_radius = int(''.join(filter(str.isdigit, radius_response)))
        except Exception as e:
            print(f"Radius LLM error: {e}")
            search_radius = 10 

    # --- STEP 3: Geographic Filtering (SQL) ---
    geo_query = text("""
        SELECT user_id FROM locationapp_location 
        WHERE (6371 * acos(cos(radians(:lat)) * cos(radians(latitude)) * cos(radians(longitude) - radians(:lng)) + 
               sin(radians(:lat)) * sin(radians(latitude)))) <= :radius
    """)
    nearby_rows = db.execute(geo_query, {"lat": emp_lat, "lng": emp_lng, "radius": search_radius}).fetchall()
    nearby_ids = [row[0] for row in nearby_rows]

    # --- STEP 4: Semantic Retrieval & Filtering ---
    final_matches = []
    if nearby_ids and vector_db:
        try:
            # Use the globally loaded index
            docs = vector_db.similarity_search(query, k=30)
            
            # Filter matches to only those physically nearby
            final_matches = [
                doc.page_content for doc in docs 
                if doc.metadata.get("worker_id") in nearby_ids
            ]
        except Exception as e:
            print(f"Vector search error: {e}")

    # --- STEP 5: SYNC COUNTS ---
    total_found = len(final_matches)
    context_to_send = "\n---\n".join(final_matches[:3])

    # --- STEP 6: The AI Assistant Brain ---
    system_instruction = f"""
    You are the Hustlr AI Assistant. 
    You MUST begin your response by saying: "I found {total_found} worker(s) within {search_radius}km..."
    
    INSTRUCTIONS:
    1. Summarize the profiles in the context.
    2. If a bio is very short (like "very gud"), explain that the worker is available but their full profile is still being updated.
    3. Be brief and professional.
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_instruction),
        ("human", "Context:\n{context}\n\nUser Question: {query}")
    ])

    ai_response_content = f"I found {total_found} worker(s) within {search_radius}km. Unfortunately, I am currently over my AI request quota for the day, so I cannot provide a detailed summary. Please try again later or contact support."
    
    try:
        chain = prompt | llm
        ai_response = chain.invoke({
            "context": context_to_send if final_matches else "No matching workers found.",
            "query": query
        })
        ai_response_content = ai_response.content
    except Exception as e:
        print(f"AI Brain Quota/Error: {e}")
        # Fallback is already set above

    return {
        "answer": ai_response_content,
        "search_radius_used": search_radius,
        "workers_in_range_count": total_found 
    }
