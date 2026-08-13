from pydantic import BaseModel
from datetime import datetime

class WeatherForecastResponse(BaseModel):
    id: int
    station_id: int
    timestamp: datetime
    temperature: float
    cloud_cover: float
    pressure: float
    humidity: float
    wind_speed: float
    source: str
    
    st_s: int
    h_svetl: float
    azimuth: float
    elevation: float
    day_of_week: int
    ww: float
    
    created_at: datetime

    class Config:
        from_attributes = True
