from pydantic import BaseModel, Field
from datetime import datetime

class StationBase(BaseModel):
    """Базова Pydantic-схема з валідацією типів"""
    name: str = Field(..., description="Назва сонячної електростанції")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Географічна широта")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Географічна довгота")
    installed_capacity_kw: float = Field(..., gt=0, description="Потужність СЕС у кВт")

class StationCreate(StationBase):
    """Схема для створення нової станції"""
    pass

class StationResponse(StationBase):
    """Схема для відповіді API (з id та строгим типом)"""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
