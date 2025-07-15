from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import os
from typing import List

from .model_handler import text_summarization_handler, TextSummarizationRequest

app = FastAPI(
    title="Text Summarization Server",
    description="Provides text summarization using distilbert/distilgpt2 model based on a prompt.",
    version="0.1.0"
)

DEBUG_MODE = os.environ.get("DEBUG_MODE", "False").lower() == "true"

@app.on_event("startup")
async def startup_event():
    if text_summarization_handler.generator is None:
        print("Model could not be loaded at startup. Generation endpoint will fail.")
    else:
        print("Text Summarization Server started. Model is ready.")

@app.post("/generate/", summary="Generate text based on a prompt", response_model=List[str])
async def run_text_summarization(request: TextSummarizationRequest):
    """
    Receives a prompt and other parameters, returns generated text sequences.
    """
    if text_summarization_handler.generator is None:
        raise HTTPException(status_code=503, detail="Model is not available. Please check server logs.")

    try:
        generated_texts = await text_summarization_handler.generate_text(request)
        
        if generated_texts and generated_texts[0].startswith("Error:"):
            raise HTTPException(status_code=500, detail=generated_texts[0])
            
        return generated_texts 
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Unexpected error in /generate/ endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/health", summary="Health check endpoint")
async def health_check():
    return {"status": "ok", "model_loaded": text_summarization_handler.generator is not None}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 