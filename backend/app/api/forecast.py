from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.forecast_service import generate_power_forecast_for_station, get_saved_forecast_for_station

DbSessionDep = Annotated[Session, Depends(get_db)]

router = APIRouter(
    prefix="/forecast",
    tags=["Прогноз Генерації (Forecast)"]
)


@router.get("/{station_id}", status_code=status.HTTP_200_OK)
def get_forecast(
        station_id: int,
        db: DbSessionDep,
        weather_source: str = "OpenWeatherMap",
        date_param: Optional[date] = Query(None, alias="date", description="Фільтр по даті (YYYY-MM-DD)")
):
    """Отримати збережений прогноз генерації з БД Neon для вказаного джерела погоди та дати"""
    results = get_saved_forecast_for_station(db, station_id, target_date=date_param, weather_source=weather_source)
    return {
        "status": "success",
        "station_id": station_id,
        "count": len(results),
        "data": results
    }


@router.post("/generate/{station_id}", status_code=status.HTTP_200_OK)
def generate_forecast(
        station_id: int,
        db: DbSessionDep,
        weather_source: str = "OpenWeatherMap",
        model_id: Optional[int] = None,
        date_param: Optional[date] = Query(None, alias="date", description="Дата для розрахунку прогнозу (YYYY-MM-DD)")
):
    """Розрахувати прогноз генерації за обраним джерелом погоди, датою та моделлю"""
    results = generate_power_forecast_for_station(
        db,
        station_id,
        target_date=date_param,
        weather_source=weather_source,
        model_id=model_id
    )
    return {
        "status": "success",
        "station_id": station_id,
        "count": len(results),
        "data": results
    }
