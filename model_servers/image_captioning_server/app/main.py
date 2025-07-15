from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import os

from .model_handler import captioning_handler

app = FastAPI(
    title="Image Captioning Server",
    description="Provides image captioning using nlpconnect/vit-gpt2-image-captioning model.",
    version="0.1.0"
)

DEBUG_MODE = os.environ.get("DEBUG_MODE", "False").lower() == "true"

@app.on_event("startup")
async def startup_event():
    if captioning_handler.captioner is None:
        print("Model could not be loaded at startup. Captioning endpoint will fail.")
    else:
        print("Image Captioning Server started. Model is ready.")

@app.post("/caption/", summary="Generate a caption for an image")
async def generate_caption(file: UploadFile = File(...) ):
    """
    Receives an image file and returns a generated caption.
    """
    if captioning_handler.captioner is None:
        raise HTTPException(status_code=503, detail="Model is not available. Please check server logs.")

    try:
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="No image data received.")
        
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}. Please upload an image.")

        caption = await captioning_handler.get_caption(image_bytes)
        
        if caption.startswith("Error:"):
             raise HTTPException(status_code=500, detail=caption)
        return JSONResponse(content={"filename": file.filename, "caption": caption})
    except HTTPException as e: 
        raise e
    except Exception as e:
        print(f"Unexpected error in /caption/ endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/health", summary="Health check endpoint")
async def health_check():
    """
    Simple health check endpoint.
    """
    return {"status": "ok", "model_loaded": captioning_handler.captioner is not None}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 