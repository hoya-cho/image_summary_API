import httpx 
import aiohttp 
import os
from datetime import datetime, date
from typing import Optional, Tuple, Dict, Any, List
import uuid
import asyncio 
import logging

from ..models.schemas import (
    QueuedItem, ImageSummaryRecord, DailyUsage,
    CaptionData, DetectedObjectsData, TextSummarizationInput
)
from .queue_manager import queue_manager
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import ConnectionFailure, OperationFailure

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables for service URLs and DB config
IMAGE_CAPTIONING_URL = os.getenv("IMAGE_CAPTIONING_URL", "http://localhost:8001/caption/")
OBJECT_DETECTION_URL = os.getenv("OBJECT_DETECTION_URL", "http://localhost:8002/detect/")
TEXT_SUMMARIZATION_URL = os.getenv("TEXT_SUMMARIZATION_URL", "http://localhost:8003/generate/")

MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "image_summary_db")
MONGO_USER = os.getenv("MONGO_INITDB_ROOT_USERNAME", "mongoadmin")
MONGO_PASS = os.getenv("MONGO_INITDB_ROOT_PASSWORD", "secret")

MAX_SUMMARIES_PER_DAY = int(os.getenv("MAX_SUMMARIES_PER_DAY", 20))
MAX_PARTICIPATION_WITH_SHARES = int(os.getenv("MAX_PARTICIPATION_WITH_SHARES", 4))

# MongoDB Client Setup
# Construct the MongoDB URI
mongo_uri = f"mongodb://{MONGO_HOST}:{MONGO_PORT}/"
try:
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    client.admin.command('ping') # Verify connection
    db = client[MONGO_DB_NAME]
    image_summaries_collection = db["image_summaries"]
    daily_usage_collection = db["daily_usage"]
    # Create indexes if they don't exist for faster queries
    image_summaries_collection.create_index([("customer_id", 1), ("created_at", -1)])
    image_summaries_collection.create_index([("sequence_number", 1)], unique=True)
    daily_usage_collection.create_index([("customer_id", 1), ("date", 1)], unique=True)
    logger.info(f"Successfully connected to MongoDB: {MONGO_HOST}:{MONGO_PORT}")
except ConnectionFailure:
    logger.error(f"Failed to connect to MongoDB: {MONGO_HOST}:{MONGO_PORT}. Check connection settings and Docker service.")
    db = None # Indicate DB is not available
    image_summaries_collection = None
    daily_usage_collection = None

async def get_next_sequence_number() -> int:
    if db is None:
        raise OperationFailure("MongoDB not connected.")
    counter_collection = db["counters"]
    sequence_doc = counter_collection.find_one_and_update(
        {"_id": "summary_sequence"},
        {"$inc": {"sequence_value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return sequence_doc["sequence_value"]

def increment_and_check_total_summaries_today() -> bool:
    today_str = date.today().isoformat()
    counter_collection = db["counters"]
    result = counter_collection.find_one_and_update(
        {"_id": f"summary_total_{today_str}"},
        {"$inc": {"count": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    if result["count"] > MAX_SUMMARIES_PER_DAY:
        # 이미 20회를 넘었으니 롤백
        counter_collection.update_one(
            {"_id": f"summary_total_{today_str}"},
            {"$inc": {"count": -1}}
        )
        return False
    return True

async def check_user_limits(customer_id: str) -> Tuple[bool, str, bool]:
    """
    Checks if the user can participate based on daily limits and shared attempts.
    Returns: (can_participate, message, is_first_time_today_or_shared_opportunity)
    """
    if daily_usage_collection is None or db is None:
        return False, "Database service not available.", False

    # 전체 합산 20회 제한 
    if not increment_and_check_total_summaries_today():
        return False, f"Total daily summary limit ({MAX_SUMMARIES_PER_DAY}) reached for today.", False

    today_str = date.today().isoformat()
    usage = daily_usage_collection.find_one({"customer_id": customer_id, "date": today_str})

    is_first_time = True
    can_participate_overall = True

    if usage:
        is_first_time = False
        if usage["participation_count"] >= MAX_PARTICIPATION_WITH_SHARES:
            # 참여 제한에 걸리면 카운터 롤백
            counter_collection = db["counters"]
            counter_collection.update_one(
                {"_id": f"summary_total_{today_str}"},
                {"$inc": {"count": -1}}
            )
            return False, f"Maximum participation limit ({MAX_PARTICIPATION_WITH_SHARES}), including shares, reached.", False

    current_participation_count = usage["participation_count"] if usage else 0
    prioritize_in_queue = (current_participation_count == 0)

    return can_participate_overall, "Participation allowed.", prioritize_in_queue

async def update_user_usage(customer_id: str, is_new_participation_slot: bool):
    """
    Updates the user's daily summary count and participation count.
    is_new_participation_slot: True if this usage consumes one of the MAX_PARTICIPATION_WITH_SHARES slots.
                                 Set to False if it's just an additional summary within an existing participation slot (not strictly needed by current rules but good for clarity).
                                 The problem statement implies each accepted photo counts as a participation towards MAX_PARTICIPATION_WITH_SHARES.
    """
    if daily_usage_collection is None:
        logger.warning("Cannot update user usage, DB not available.")
        return

    today_str = date.today().isoformat()
    update_doc = {"$inc": {"summary_count": 1}}
    if is_new_participation_slot:
        update_doc["$inc"]["participation_count"] = 1
    
    result = daily_usage_collection.update_one(
        {"customer_id": customer_id, "date": today_str},
        update_doc,
        upsert=True
    )
    if result.upserted_id or result.modified_count > 0:
        logger.info(f"Updated usage for customer {customer_id} on {today_str}.")
    else:
        logger.warning(f"Failed to update usage for customer {customer_id} on {today_str} or no change needed.")


async def process_image_submission(customer_id: str, file_name: str, image_bytes: bytes) -> Tuple[bool, str, Optional[str]]:
    """
    Handles the image submission, adds to queue after validation.
    Returns: (success, message, request_id)
    """
    try:
        if not image_bytes:
            return False, "Image data is empty.", None
        
        can_participate, message, is_priority_user = await check_user_limits(customer_id)
        if not can_participate:
            return False, message, None

        request_id = str(uuid.uuid4())
        queued_item = QueuedItem(
            request_id=request_id,
            customer_id=customer_id,
            file_name=file_name,
            image_bytes=image_bytes, # Store bytes directly
            is_first_time_user=is_priority_user 
        )
        
        await queue_manager.add_to_queue(queued_item)
        logger.info(f"Request {request_id} for customer {customer_id} added to queue.")
        
        await update_user_usage(customer_id, is_new_participation_slot=True)

        return True, "Request accepted and queued for processing.", request_id
    except OperationFailure as e:
        logger.error(f"MongoDB operation failed during image submission: {e}")
        return False, "Database error during submission.", None
    except Exception as e:
        logger.error(f"Error processing image submission for customer {customer_id}: {e}")
        return False, f"An unexpected error occurred: {str(e)}", None


async def call_model_server(client_session: aiohttp.ClientSession, url: str, data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Helper function to call a model server.
    `data` is for JSON payload (like for text generation).
    `files` is for multipart/form-data (like for image uploads).
    """
    try:
        if files: # For image captioning and object detection
            form = aiohttp.FormData()
            for key, (filename, file_bytes, content_type) in files.items():
                form.add_field(key, file_bytes, filename=filename, content_type=content_type)
            async with client_session.post(url, data=form) as response:
                response.raise_for_status()
                return await response.json()
        elif data: # For text generation
            async with client_session.post(url, json=data) as response:
                response.raise_for_status()
                return await response.json()
        else: # Should not happen with current model server designs
            logger.warning(f"call_model_server called with no data or files for URL: {url}")
            return None
    except aiohttp.ClientResponseError as e:
        logger.error(f"HTTP error calling {url}: {e.status} {e.message} - Response: {await e.response.text() if e.response else 'No response text'}")
    except aiohttp.ClientConnectionError as e:
        logger.error(f"Connection error calling {url}: {e}")
    except asyncio.TimeoutError:
        logger.error(f"Timeout error calling {url}")
    except Exception as e:
        logger.error(f"Generic error calling {url}: {e}")
    return None

async def process_single_item_from_queue(item: QueuedItem):
    """
    Processes a single item from the queue: calls models, generates summary, saves to DB.
    """
    logger.info(f"Processing item {item.request_id} for customer {item.customer_id}...")
    try:
        async with aiohttp.ClientSession() as session:
            # 1. Image Captioning
            caption_files = {'file': (item.file_name, item.image_bytes, 'image/jpeg')} # Assuming jpeg, can be more dynamic
            caption_response_json = await call_model_server(session, IMAGE_CAPTIONING_URL, files=caption_files)
            caption_data = CaptionData(**caption_response_json) if caption_response_json and "caption" in caption_response_json else None
            image_caption = caption_data.caption if caption_data else "Captioning failed or not available."
            logger.info(f"Item {item.request_id}: Caption - '{image_caption}'")

            # 2. Object Detection
            detection_files = {'file': (item.file_name, item.image_bytes, 'image/jpeg')}
            detection_response_json = await call_model_server(session, OBJECT_DETECTION_URL, files=detection_files)
            detected_objects_data = DetectedObjectsData(**detection_response_json) if detection_response_json and "objects" in detection_response_json else None
            objects_list = detected_objects_data.objects if detected_objects_data else []
            logger.info(f"Item {item.request_id}: Detected {len(objects_list)} objects.")

            # 3. Text Generation (Summary)
            prompt = f"Summarize this image. Caption: '{image_caption}'. Objects detected: "
            if objects_list:
                prompt += ", ".join([obj.label for obj in objects_list[:5]]) # Limit to 5 objects for prompt brevity
            else:
                prompt += "None."
            
            text_gen_payload = TextSummarizationInput(prompt=prompt, max_length=100).model_dump()
            summary_response_list = await call_model_server(session, TEXT_SUMMARIZATION_URL, data=text_gen_payload)
            generated_summary = summary_response_list[0] if summary_response_list and isinstance(summary_response_list, list) and summary_response_list[0] else "Summary generation failed."
            
            if generated_summary.startswith(prompt[:50]): 
                if len(generated_summary) < len(prompt) + 20 : 
                     generated_summary = f"Summary based on: {image_caption}"
            logger.info(f"Item {item.request_id}: Generated summary - '{generated_summary}'")

            # 4. Save to Database
            if image_summaries_collection is None:
                logger.error(f"Item {item.request_id}: Cannot save summary, DB not available.")
                return

            sequence_num = await get_next_sequence_number()
            summary_record = ImageSummaryRecord(
                sequence_number=sequence_num,
                customer_id=item.customer_id,
                original_file_name=item.file_name,
                text_summary=generated_summary,
                caption=image_caption,
                detected_objects=objects_list,
                created_at=datetime.utcnow()
            )
            image_summaries_collection.insert_one(summary_record.model_dump(by_alias=True))
            logger.info(f"Item {item.request_id} processed and summary saved for customer {item.customer_id} with sequence {sequence_num}.")

    except OperationFailure as e:
        logger.error(f"MongoDB operation failed while processing item {item.request_id}: {e}")
    except Exception as e:
        logger.error(f"Error processing item {item.request_id} from queue: {e}", exc_info=True)


# Background task for processing the queue
async def queue_processing_worker():
    logger.info("Queue processing worker started.")
    while True:
        try:
            item = await queue_manager.get_from_queue()
            if item:
                await process_single_item_from_queue(item)
            else:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Critical error in queue_processing_worker loop: {e}", exc_info=True)
            await asyncio.sleep(5) 

# --- Functions for retrieving data (e.g., for user app) ---
async def get_summary_by_customer_and_filename(customer_id: str, filename: str) -> Optional[ImageSummaryRecord]:
    if image_summaries_collection is None:
        logger.warning("Cannot retrieve summary, DB not available.")
        return None
    doc = image_summaries_collection.find_one({"customer_id": customer_id, "original_file_name": filename}, sort=[("created_at", -1)])
    return ImageSummaryRecord(**doc) if doc else None

async def get_summaries_by_customer(customer_id: str, limit: int = 10) -> List[ImageSummaryRecord]:
    if image_summaries_collection is None:
        logger.warning("Cannot retrieve summaries, DB not available.")
        return []
    cursor = image_summaries_collection.find({"customer_id": customer_id}).sort("created_at", -1).limit(limit)
    return [ImageSummaryRecord(**doc) for doc in await cursor.to_list(length=limit)]


async def get_all_summaries(limit: int = 100) -> List[ImageSummaryRecord]: # For debug
    if image_summaries_collection is None:
        return []
    cursor = image_summaries_collection.find().sort("created_at", -1).limit(limit)
    return [ImageSummaryRecord(**doc) for doc in await cursor.to_list(length=limit)] 

def get_total_summaries_today() -> int:
    today = date.today()
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time())
    return image_summaries_collection.count_documents({
        "created_at": {"$gte": start, "$lte": end}
    }) 