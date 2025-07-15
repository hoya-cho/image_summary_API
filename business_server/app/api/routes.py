from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional
import logging

from ..core import services
from ..core.queue_manager import queue_manager 
from ..models.schemas import ImageUploadResponse, ImageSummaryRecord, QueuedItem

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Dependency to check DB connection status (simplified)
def get_db_status():
    if services.db is None:
        raise HTTPException(status_code=503, detail="Database service is not available. Please check server logs.")
    return True

@router.post("/upload_image/", 
             response_model=ImageUploadResponse, 
             summary="Upload an image for text summarization")
async def upload_image(
    background_tasks: BackgroundTasks, 
    customer_id: str = Form(...),
    image: UploadFile = File(...),
    db_available: bool = Depends(get_db_status) # Check DB before proceeding
):
    """
    Receives an image and customer ID. Validates the request, checks user limits,
    adds the image to a processing queue, and returns an immediate acknowledgment.

    - **customer_id**: The unique identifier for the customer.
    - **image**: The image file to be processed.
    """
    logger.info(f"Received image upload request for customer_id: {customer_id}, filename: {image.filename}")

    # Basic file validation (can be more sophisticated)
    if not image.content_type.startswith("image/"):
        logger.warning(f"Invalid file type for customer {customer_id}: {image.content_type}")
        return ImageUploadResponse(success=False, message="Invalid file type. Please upload an image (JPEG, PNG, etc.).", error_info="Unsupported content type")
    
    image_bytes = await image.read()
    if not image_bytes:
        logger.warning(f"Empty image file uploaded by customer {customer_id}.")
        return ImageUploadResponse(success=False, message="Image file is empty.", error_info="Empty file")

    try:
        success, message, request_id = await services.process_image_submission(
            customer_id=customer_id, 
            file_name=image.filename, 
            image_bytes=image_bytes
        )
        
        if success:
            logger.info(f"Image from {customer_id} ({image.filename}) accepted. Request ID: {request_id}")
            return ImageUploadResponse(success=True, message=message, request_id=request_id)
        else:
            logger.warning(f"Image submission failed for {customer_id} ({image.filename}): {message}")
            status_code = 429 if "limit" in message.lower() else 400
            return JSONResponse(
                status_code=status_code,
                content=ImageUploadResponse(success=False, message=message, error_info=message).model_dump()
            )

    except Exception as e:
        logger.error(f"Unexpected error during image upload for customer {customer_id}: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=ImageUploadResponse(success=False, message="An unexpected server error occurred.", error_info=str(e)).model_dump()
        )

@router.get("/summaries/{customer_id}", 
            response_model=List[ImageSummaryRecord], 
            summary="Get summaries for a customer")
async def get_customer_summaries(customer_id: str, limit: int = 10, db_available: bool = Depends(get_db_status)):
    """
    Retrieves the latest image summaries for a given customer.
    """
    logger.info(f"Fetching summaries for customer_id: {customer_id}, limit: {limit}")
    try:
        summaries = await services.get_summaries_by_customer(customer_id, limit)
        return summaries
    except Exception as e:
        logger.error(f"Error fetching summaries for customer {customer_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve summaries.")

@router.get("/summary/{customer_id}/{filename}", 
            response_model=Optional[ImageSummaryRecord], 
            summary="Get a specific summary by customer and filename")
async def get_specific_summary(customer_id: str, filename: str, db_available: bool = Depends(get_db_status)):
    """
    Retrieves a specific image summary for a customer by filename.
    Note: If multiple uploads with the same filename, returns the latest.
    """
    logger.info(f"Fetching summary for customer_id: {customer_id}, filename: {filename}")
    try:
        summary = await services.get_summary_by_customer_and_filename(customer_id, filename)
        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found.")
        return summary
    except HTTPException as e:
        raise e # Re-raise HTTPException
    except Exception as e:
        logger.error(f"Error fetching specific summary for {customer_id}, {filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve summary.")

@router.get("/admin/queue_status/", summary="Get current queue status (Admin)")
async def get_queue_info():
    status = await queue_manager.get_queue_status()
    return status

@router.get("/admin/all_queued_items/", response_model=List[QueuedItem], summary="Get all items currently in queue (Admin)")
async def get_all_queued_items_snapshot():
    items = queue_manager.get_all_items_snapshot()
    return items

@router.get("/admin/all_summaries/", response_model=List[ImageSummaryRecord], summary="Get all processed summaries (Admin)")
async def get_all_processed_summaries(limit: int = 50, db_available: bool = Depends(get_db_status)):
    logger.info(f"Fetching all summaries, limit: {limit}")
    try:
        summaries = await services.get_all_summaries(limit)
        return summaries
    except Exception as e:
        logger.error(f"Error fetching all summaries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve all summaries.") 