from transformers import pipeline
from PIL import Image
import io

class ImageCaptioningHandler:
    def __init__(self):
        # Load the model
        try:
            self.captioner = pipeline("image-to-text", model="nlpconnect/vit-gpt2-image-captioning", device=-1)
            print("Image captioning model loaded successfully.")
        except Exception as e:
            print(f"Error loading image captioning model: {e}")
            self.captioner = None

    async def get_caption(self, image_bytes: bytes) -> str:
        if not self.captioner:
            return "Error: Model not loaded."
        try:
            image = Image.open(io.BytesIO(image_bytes))
            if image.mode != "RGB":
                image = image.convert("RGB")
            caption_result = self.captioner(image)
            return caption_result[0]["generated_text"]
        except Exception as e:
            print(f"Error during image captioning: {e}")
            return f"Error processing image: {str(e)}"

captioning_handler = ImageCaptioningHandler() 