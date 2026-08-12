from typing import Annotated, List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.generation import GenerationForecast
from app.schemas.generation import GenerationForecastResponse
from app.services.forecast_service import generate_power_forecast

DbSessionDep = Annotated[Session, Depends(get_db)]

router = APIRouter(
    prefix="/forecast",
    tags=["Прогноз Генерації СЕС (Generation Forecast)"]
)

@router.post("/generate/{station_id}", response_model=List[GenerationForecastResponse], status_code=status.HTTP_200_OK)
def generate_forecast(station_id: int, db: DbSessionDep):
    """Сформувати та зберегти прогноз генерації (кВт) нейромережею для станції"""
    forecasts = generate_power_forecast(db, station_id)
    return forecasts

@router.get("/{station_id}", response_model=List[GenerationForecastResponse])
def get_generation_forecast(station_id: int, db: DbSessionDep):
    """Отримати збережений прогноз генерації електроенергії з бази даних"""
    forecasts = db.query(GenerationForecast).filter(
        GenerationForecast.station_id == station_id
    ).order_by(GenerationForecast.timestamp.asc()).all()
    return forecasts
