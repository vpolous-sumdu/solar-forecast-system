from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class GenerationForecastResponse(BaseModel):
    id: int
    station_id: int
    model_id: Optional[int]
    timestamp: datetime
    predicted_power_kw: float
    created_at: datetime

    class Config:
        from_attributes = True
