from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.search_router import router as search_router

import threading
from contextlib import asynccontextmanager
from services.user_consumer import start_user_sync_consumer

@asynccontextmanager
async def lifespan(app:FastAPI):

    # daemon=True means the thread will automatically die when you stop the main app
    consumer_thread = threading.Thread(target=start_user_sync_consumer,daemon=True)
    consumer_thread.start()
    print("🚀 AI Service: RabbitMQ Background Consumer started!")

    yield  # The app runs here...

    # --- SHUTDOWN ---
    print("Stopping AI Service...")

app = FastAPI(root_path="/ai",lifespan=lifespan)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://hustlrs-ivory.vercel.app",
        "https://hustlrr.duckdns.org",
        "https://hustlrr.duckdns.org:30443"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




app.include_router(search_router)
