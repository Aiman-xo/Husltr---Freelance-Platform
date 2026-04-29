import os
import re
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_groq import ChatGroq
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate

# Load environment variables from the parent/backend .env
load_dotenv(dotenv_path="../Hustlr-backend/.env")
# Fallback to local .env if specific keys (like Groq) are there
load_dotenv()

# 1. Initialize Gemini Embeddings
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

# 2. Initialize Groq LLM (LLAMA 3.1 8B Instant)
llm = ChatGroq(model="llama-3.1-8b-instant")

# 3. Global FAISS Loading (Saves significant time per request)
# 3. Global FAISS Loading (Resilient)
vector_db = None

def load_or_sync_index():
    global vector_db
    from services.sync_service import run_vector_sync
    
    try:
        if os.path.exists("faiss_index"):
            print("Attempting to load existing FAISS index...")
            vector_db = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
            print("FAISS index loaded successfully.")
        else:
            print("FAISS index not found. Performing initial sync...")
            run_vector_sync()
    except Exception as e:
        print(f"Index loading error: {e}. Attempting recovery sync...")
        run_vector_sync()

# Initial load attempt
load_or_sync_index()

def is_greeting(query: str) -> bool:
    """Checks if the query is a simple greeting and NOTHING else."""
    greetings = ["hi", "hello", "good morning", "good afternoon", "good evening", "hey", "greetings", "hii", "heyo", "howdy", "hola"]
    # clean query keeping only letters and spaces
    cleaned = re.sub(r'[^a-zA-Z\s]', '', query.lower()).strip()
    # IF the query contains "want", "find", "need", "looking", "worker", "cleaner" etc, it's NOT a simple greeting
    search_keywords = ["want", "find", "need", "look", "worker", "cleaner", "plumber", "electrician", "help"]
    if any(word in cleaned for word in search_keywords):
        return False
    return cleaned in greetings

def extract_radius(query: str) -> int:
    """Try to extract radius using regex to avoid an extra LLM call."""
    # Matches patterns like "5km", "10 km", "within 20 kilometers"
    matches = re.findall(r"(\d+)\s*(?:km|kilometer|km\b)", query.lower())
    if matches:
        return int(matches[0])
        
    try:
        dist_prompt = f"Extract only the search radius in km from this query: '{query}'. If no distance or 'nearby' is mentioned, return 1000. Return ONLY the number."
        radius_raw = llm.invoke(dist_prompt).content
        radius_response = radius_raw.strip()
        search_radius = int(''.join(filter(str.isdigit, radius_response)))
        if search_radius <= 0:
            return 1000
        return search_radius
    except Exception as e:
        print(f"Radius LLM error: {e}")
        return 1000

def generate_ai_response(query: str, search_radius: int, final_matches: list,user_role:str) -> str:
    total_found = len(final_matches)
    context_to_send = "\n---\n".join(final_matches[:3])

    if user_role == "employer":
        target_noun = "worker(s)"
        goal_text = "finding local workers for their tasks"
        identity = "an assistant for employers"
    else:
        target_noun = "job(s)"
        goal_text = "finding local job opportunities for them to apply to"
        identity = "an assistant for workers"
    
    system_instruction = f"""
    You are the Hustlr AI Assistant {identity}, Your goal is to assist the user in {goal_text}. 
    
    CRITICAL INSTRUCTIONS:
    
    1. IF THE USER IS JUST GREETING YOU (e.g., "hi", "helloo"):
       - Respond with a friendly greeting and ask how you can help them { "find workers" if user_role == "employer" else "find a job" }.
       
    2. IF WORKER DATA IS PROVIDED IN THE CONTEXT:
       - You MUST begin your response exactly by saying: "I found {total_found} {target_noun} within {search_radius}km..."
       - Summarize the {target_noun}. Do not invent any workers.
       
    3. IF NO WORKERS ARE FOUND BUT THE USER IS SEARCHING:
       - Say "I found 0 {target_noun} within {search_radius}km." 
       - Suggest they increase their search radius or check back later.
    
    4. FORMATTING RULES:
       - Use Markdown **bolding** for Job Titles, Employer Names, and Skills.
       - If the context already contains text wrapped in **, PRESERVE it in your response.
       - Ensure your output is easy to read using bullet points for lists of jobs.
       
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_instruction),
        ("human", "Context:\n{context}\n\nUser Question: {query}")
    ])

    try:
        chain = prompt | llm
        ai_response = chain.invoke({
            "context": context_to_send if final_matches else "No matching workers found.",
            "query": query
        })
        return ai_response.content
    except Exception as e:
        print(f"AI Brain Quota/Error: {e}")
        return f"I found {total_found} {target_noun} within {search_radius}km. Unfortunately, there was an issue connecting to the AI brain. Please try again later or contact support."
