from pydantic import BaseModel, Field, validator
from typing import Optional, List, Any, Dict
from datetime import datetime

class ImageUploadRequest(BaseModel):
    customer_id: str = Field(..., example="user_00001", description="Unique customer identifier")

class ImageUploadResponse(BaseModel):
    success: bool
    message: str
    request_id: Optional[str] = None
    error_info: Optional[str] = None

class QueuedItem(BaseModel):
    request_id: str
    customer_id: str
    file_name: str
    image_bytes: bytes 
    received_at: datetime = Field(default_factory=datetime.utcnow)
    is_first_time_user: bool = True 

    class Config:
        arbitrary_types_allowed = True 


class CaptionData(BaseModel):
    filename: str
    caption: str

class ObjectData(BaseModel):
    label: str
    score: float
    box: Dict[str, int]  # [xmin, ymin, xmax, ymax]

class DetectedObjectsData(BaseModel):
    filename: str
    objects: List[ObjectData]

class TextSummarizationInput(BaseModel):
    prompt: str
    max_length: int = 150 # Default length for summary
    num_return_sequences: int = 1

# --- Database Schema ---
class ImageSummaryRecord(BaseModel):
    # id: Optional[str] = Field(None, alias="_id")
    sequence_number: int 
    customer_id: str
    original_file_name: str
    text_summary: str
    caption: Optional[str] = None
    detected_objects: Optional[List[ObjectData]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    

class DailyUsage(BaseModel):
    # id: Optional[str] = Field(None, alias="_id")
    customer_id: str
    date: str # YYYY-MM-DD
    summary_count: int = 0
    participation_count: int = 0 

    @validator("date")
    def validate_date_format(cls, value):
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")
        return value 