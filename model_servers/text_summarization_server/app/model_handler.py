from transformers import pipeline, set_seed
from pydantic import BaseModel, Field
from typing import List

class TextSummarizationRequest(BaseModel):
    prompt: str = Field(..., example="A picture of a cat sitting on a table. Objects found: cat, table.")
    max_length: int = Field(default=100, gt=0, le=500)
    num_return_sequences: int = Field(default=1, gt=0, le=5)

class TextSummarizationHandler:
    def __init__(self):
        try:
            self.generator = pipeline("text-generation", model="distilbert/distilgpt2", device=-1)
            set_seed(42) # For reproducibility
            print("Text summarization model (distilbert/distilgpt2) loaded successfully.")
        except Exception as e:
            print(f"Error loading text summarization model: {e}")
            self.generator = None

    async def generate_text(self, request: TextSummarizationRequest) -> List[str]:
        if not self.generator:
            return ["Error: Model not loaded."]
        try:
            generated_outputs = self.generator(
                request.prompt,
                max_length=request.max_length,
                num_return_sequences=request.num_return_sequences
            )
            return [output["generated_text"] for output in generated_outputs]
        except Exception as e:
            print(f"Error during text summarization: {e}")
            return [f"Error generating text: {str(e)}"]

text_summarization_handler = TextSummarizationHandler() 