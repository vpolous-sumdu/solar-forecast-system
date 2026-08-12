from typing import Annotated, List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.weather import WeatherForecast
from app.schemas.weather import WeatherForecastResponse
from app.services.weather_service import fetch_and_save_weather

DbSessionDep = Annotated[Session, Depends(get_db)]

router = APIRouter(
    prefix="/weather",
    tags=["Прогноз Погоди (Weather)"]
)

@router.post("/fetch/{station_id}", status_code=status.HTTP_200_OK)
def fetch_weather(station_id: int, db: DbSessionDep):
    """Завантажити свіжий прогноз погоди з Open-Meteo та зберегти у Neon DB"""
    saved_count = fetch_and_save_weather(db, station_id)
    return {
        "status": "success",
        "message": f"Збережено/оновлено {saved_count} годинних записів погоди для станції #{station_id}"
    }

@router.get("/{station_id}", response_model=List[WeatherForecastResponse])
def get_weather_forecast(station_id: int, db: DbSessionDep):
    """Отримати збережений прогноз погоди для обраної СЕС з бази даних"""
    forecasts = db.query(WeatherForecast).filter(
        WeatherForecast.station_id == station_id
    ).order_by(WeatherForecast.timestamp.asc()).all()
    return forecasts
