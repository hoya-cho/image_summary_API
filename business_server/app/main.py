from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio 
import os
import logging
from dotenv import load_dotenv

load_dotenv()

from .api import routes as api_routes
from .core import services # To access queue_processing_worker
from .core.queue_manager import queue_manager # For startup message

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Image Summary Event - Business Server",
    description="Handles image uploads, queues processing, and provides results.",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.on_event("startup")
async def startup_event():
    logger.info("Business Server starting up...")
    # Verify DB connection on startup (optional, already done in services.py)
    if services.db is None:
        logger.critical("MongoDB connection failed. Business logic dependent on DB will not work.")
    else:
        logger.info("MongoDB connection verified.")
    
    # Start the background worker for queue processing
    asyncio.create_task(services.queue_processing_worker())
    logger.info("Background queue processing worker started.")
    initial_queue_status = await queue_manager.get_queue_status()
    logger.info(f"Initial queue status: {initial_queue_status}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Business Server shutting down...")
    if services.client: # Pymongo client
        services.client.close()
        logger.info("MongoDB connection closed.")

# Include API routes
app.include_router(api_routes.router, prefix="/api", tags=["Image Processing"])

@app.get("/health", summary="Health check for Business Server")
async def health_check():
    # Basic health check, can be expanded to check DB, queue status etc.
    db_status = "connected" if services.db else "disconnected"
    queue_status = await queue_manager.get_queue_status()
    return {
        "status": "ok", 
        "message": "Business Server is running", 
        "database_status": db_status,
        "queue_items": queue_status.get("total_items", 0)
    }

if __name__ == "__main__":

    DEBUG_MODE = os.environ.get("DEBUG_MODE", "False").lower() == "true"
    uvicorn_kwargs = {"host": "0.0.0.0", "port": 8000}
    if DEBUG_MODE:
        uvicorn_kwargs["reload"] = True
        logger.info("Running in DEBUG mode with reload enabled.")
    
    import uvicorn
    uvicorn.run("main:app", **uvicorn_kwargs) 