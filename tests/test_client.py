import asyncio
import aiohttp
import os
import glob
from dotenv import load_dotenv
import logging
from typing import List, Dict, Any, Tuple
import sys

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from the project's .env file
# Assuming the .env file is in the parent directory of the 'tests' directory
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

BUSINESS_SERVER_HOST = os.getenv("BUSINESS_SERVER_HOST", "localhost")
BUSINESS_SERVER_PORT = os.getenv("BUSINESS_SERVER_PORT", "8000")
UPLOAD_URL = f"http://{BUSINESS_SERVER_HOST}:{BUSINESS_SERVER_PORT}/api/upload_image/"

# Directory containing sample images for testing
# This path is relative to the location of test_client.py
SAMPLE_IMAGES_DIR = os.path.join(os.path.dirname(__file__), "sample_images")

def get_customer_id_from_filename(filename: str) -> str:
    """Extracts customer ID (padded 5-digit number before extension) from filename."""
    base = os.path.splitext(os.path.basename(filename))[0]
    # Assuming format like 'some_name_XXXXX'
    parts = base.split('_')
    if parts:
        numeric_part = parts[-1]
        if numeric_part.isdigit() and len(numeric_part) >= 5:
            return numeric_part[-5:] # Last 5 digits
    # Fallback or more robust parsing needed if format varies
    # For now, using a simple default if parsing fails
    return "00000" 

async def upload_image(session: aiohttp.ClientSession, image_path: str) -> Dict[str, Any]:
    """Uploads a single image to the business server."""
    filename = os.path.basename(image_path)
    customer_id = get_customer_id_from_filename(filename)
    
    # Create a dummy image content if actual image reading is not intended
    # For this test, we will send the placeholder text as if it's image data
    try:
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        if not image_bytes:
            logger.warning(f"Image file is empty: {image_path}. Skipping.")
            return {"filename": filename, "status": "skipped", "reason": "empty file"}

    except IOError as e:
        logger.error(f"Could not read image {image_path}: {e}")
        return {"filename": filename, "status": "error", "reason": str(e)}

    data = aiohttp.FormData()
    data.add_field('customer_id', customer_id)
    # The server expects 'image' as the field name for the file
    data.add_field('image', 
                   image_bytes, 
                   filename=filename, 
                   content_type='image/jpeg') # Assuming jpeg, adjust if needed or use mimetypes

    try:
        logger.info(f"Uploading {filename} for customer {customer_id}...")
        async with session.post(UPLOAD_URL, data=data) as response:
            response_json = await response.json()
            logger.info(f"Response for {filename} (Customer: {customer_id}): {response.status} - {response_json}")
            return {"filename": filename, "status_code": response.status, "response": response_json}
    except aiohttp.ClientConnectorError as e:
        logger.error(f"Connection error for {filename}: {e}")
        return {"filename": filename, "status_code": "N/A", "response": {"success": False, "message": f"Connection error: {e}"}}
    except Exception as e:
        logger.error(f"Error uploading {filename}: {e}", exc_info=True)
        return {"filename": filename, "status_code": "N/A", "response": {"success": False, "message": f"Exception: {e}"}}

async def run_concurrent_uploads(image_paths: List[str], batch_size: int = 10):
    """Runs uploads concurrently in batches."""
    async with aiohttp.ClientSession() as session:
        all_results = []
        for i in range(0, len(image_paths), batch_size):
            batch = image_paths[i:i+batch_size]
            tasks = [upload_image(session, img_path) for img_path in batch]
            results = await asyncio.gather(*tasks)
            all_results.extend(results)
            if i + batch_size < len(image_paths):
                logger.info(f"Completed batch {i//batch_size + 1}. Waiting 1 second before next batch...")
                await asyncio.sleep(1) # Small delay between batches if desired
        return all_results

def get_image_files(directory: str) -> List[str]:
    """Gets a list of image files (jpg, png, jpeg) from the specified directory, sorted."""
    extensions = ("*.jpg", "*.png", "*.jpeg")
    image_files = []
    for ext in extensions:
        image_files.extend(glob.glob(os.path.join(directory, ext)))
    image_files.sort() # Sort by filename ascending
    return image_files

async def main():
    logger.info(f"Looking for images in: {SAMPLE_IMAGES_DIR}")
    image_paths = get_image_files(SAMPLE_IMAGES_DIR)

    if not image_paths:
        logger.warning(f"No image files found in {SAMPLE_IMAGES_DIR}. Exiting test.")
        # Create some dummy files for testing if none exist
        logger.info("Creating dummy image files for testing as none were found.")
        dummy_files_info = [
            ("test_img_00001.jpg", "This is a dummy JPG image 00001."),
            ("another_pic_00002.png", "This is a dummy PNG image 00002."),
            ("sample_photo_00003.jpeg", "This is a dummy JPEG image 00003."),
            ("user_A_image_00001.jpg", "User A, first image."), # Same customer ID as first
            ("user_B_image_00005.jpg", "User B, first image."),
            # Add more to test limits if needed, up to 20 for a single user or 4 participations
            ("test_img_00006.jpg", "This is a dummy JPG image 00006."),
            ("test_img_00007.jpg", "This is a dummy JPG image 00007."),
            ("test_img_00008.jpg", "This is a dummy JPG image 00008."),
            ("test_img_00009.jpg", "This is a dummy JPG image 00009."),
            ("test_img_00010.jpg", "This is a dummy JPG image 00010."),
            ("test_img_00011.jpg", "This is a dummy JPG image 00011.") # 11th image for potential batching
        ]
        if not os.path.exists(SAMPLE_IMAGES_DIR):
            os.makedirs(SAMPLE_IMAGES_DIR)
        for name, content in dummy_files_info:
            with open(os.path.join(SAMPLE_IMAGES_DIR, name), 'w') as f:
                f.write(content)
        image_paths = get_image_files(SAMPLE_IMAGES_DIR)
        if not image_paths:
            logger.error("Still no image files found after attempting to create dummies. Exiting.")
            return
        logger.info(f"Found {len(image_paths)} images (including dummies) for testing.")
    else:
        logger.info(f"Found {len(image_paths)} images in {SAMPLE_IMAGES_DIR}.")

    logger.info(f"Target Business Server URL: {UPLOAD_URL}")
    logger.info(f"Starting concurrent uploads (10 at a time)...Total images: {len(image_paths)}")

    results = await run_concurrent_uploads(image_paths, batch_size=10)

    logger.info("\n--- Test Client Results ---")
    successful_uploads = 0
    failed_uploads = 0
    for res in results:
        if res.get("status_code") == 200 and res.get("response", {}).get("success"):
            logger.info(f"SUCCESS: {res['filename']} - {res['response']['message']} (Request ID: {res['response'].get('request_id')})")
            successful_uploads += 1
        elif res.get("status_code") == "N/A": # Connection or other pre-request errors
            logger.error(f"FAILURE: {res['filename']} - {res['response']['message']}")
            failed_uploads +=1
        elif res.get("status_code") == "skipped":
             logger.warning(f"SKIPPED: {res['filename']} - {res.get('reason')}")
        else: # HTTP error from server or success=False
            logger.error(f"FAILURE: {res['filename']} - Status: {res.get('status_code', 'N/A')} - {res.get('response', {}).get('message', 'No message')}")
            failed_uploads += 1
            
    logger.info(f"\nTotal Successful Uploads: {successful_uploads}")
    logger.info(f"Total Failed/Skipped Uploads: {failed_uploads + (len(results) - successful_uploads - failed_uploads)}")
    logger.info("Test client finished.")

if __name__ == "__main__":
    # Ensure the event loop is compatible with aiohttp if running on Windows + Python 3.8+
    if os.name == 'nt' and sys.version_info >= (3,8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main()) 