from pydantic import BaseModel, HttpUrl
from typing import Optional, List

class ReviewItemOut(BaseModel):
    id: int
    image_url: HttpUrl | str
    predicted_label: Optional[str] = None
    confidence: Optional[float] = None
    class Config: from_attributes = True

class FeedbackIn(BaseModel):
    item_id: int
    true_label: str

class ExportRow(BaseModel):
    image_url: str
    label: str
