from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class InferenceResult(BaseModel):
    stain_detected: bool
    confidence: float = Field(ge=0, le=1)
    material_type: str

class InspectionOut(BaseModel):
    instrument_name: str
    results: InferenceResult
    status: str = "processed"
    timestamp: datetime
    id: Optional[str] = None
