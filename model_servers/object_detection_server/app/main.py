from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import os

from .model_handler import object_detection_handler

app = FastAPI(
    title="Object Detection Server",
    description="Provides object detection using YOLOv12 model.",
    version="0.1.0"
)

DEBUG_MODE = os.environ.get("DEBUG_MODE", "False").lower() == "true"

@app.on_event("startup")
async def startup_event():
    if object_detection_handler.model is None:
        print("Model could not be loaded at startup. Detection endpoint will fail.")
    else:
        print("Object Detection Server started. Model is ready.")

@app.post("/detect/", summary="Detect objects in an image")
async def run_object_detection(file: UploadFile = File(...) ):
    """
    Receives an image file and returns detected objects with their scores and bounding boxes.
    """
    if object_detection_handler.model is None:
        raise HTTPException(status_code=503, detail="Model is not available. Please check server logs.")

    try:
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="No image data received.")
        
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}. Please upload an image.")

        detected_objects = await object_detection_handler.detect_objects(image_bytes)
        
        if detected_objects and isinstance(detected_objects[0], dict) and detected_objects[0].get("error"):
            raise HTTPException(status_code=500, detail=detected_objects[0]["error"])
            
        return JSONResponse(content={"filename": file.filename, "objects": detected_objects})
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Unexpected error in /detect/ endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/health", summary="Health check endpoint")
async def health_check():
    return {"status": "ok", "model_loaded": object_detection_handler.model is not None}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 