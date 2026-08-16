from typing import Annotated, List, Optional
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.weather import WeatherForecast
from app.schemas.weather import WeatherForecastResponse
from app.services.weather_service import fetch_and_save_weather, fetch_and_save_owm_weather, fetch_and_save_archive_weather

DbSessionDep = Annotated[Session, Depends(get_db)]

router = APIRouter(
    prefix="/weather",
    tags=["Прогноз Погоди (Weather)"]
)

@router.post("/fetch-open-meteo/{station_id}", status_code=status.HTTP_200_OK)
def fetch_open_meteo_weather(
    station_id: int, 
    db: DbSessionDep,
    date_param: Optional[date] = Query(None, alias="date", description="Дата для завантаження погоди (YYYY-MM-DD)")
):
    """Завантажити свіжий прогноз погоди з Open-Meteo та зберегти у Neon DB"""
    saved_count = fetch_and_save_weather(db, station_id, target_date=date_param)
    date_str = f" на дату {date_param.isoformat()}" if date_param else ""
    return {
        "status": "success",
        "message": f"Збережено/оновлено {saved_count} годинних записів погоди з Open-Meteo для станції #{station_id}{date_str}"
    }

@router.post("/fetch-open-meteo-archive/{station_id}", status_code=status.HTTP_200_OK)
def fetch_open_meteo_archive_weather(
    station_id: int, 
    db: DbSessionDep,
    date_param: Optional[date] = Query(None, alias="date", description="Дата для завантаження реальної погоди (YYYY-MM-DD)")
):
    """Завантажити фактичну (архівну) погоду з Open-Meteo Archive та зберегти у Neon DB"""
    saved_count = fetch_and_save_archive_weather(db, station_id, target_date=date_param)
    date_str = f" на дату {date_param.isoformat()}" if date_param else ""
    return {
        "status": "success",
        "message": f"Збережено/оновлено {saved_count} годинних записів реальної погоди з Open-Meteo Archive для станції #{station_id}{date_str}"
    }

@router.post("/fetch-openweathermap/{station_id}", status_code=status.HTTP_200_OK)
def fetch_openweathermap_weather(
    station_id: int, 
    db: DbSessionDep,
    date_param: Optional[date] = Query(None, alias="date", description="Дата для завантаження погоди (YYYY-MM-DD)")
):
    """Завантажити свіжий прогноз погоди з OpenWeatherMap та зберегти у Neon DB"""
    saved_count = fetch_and_save_owm_weather(db, station_id, target_date=date_param)
    date_str = f" на дату {date_param.isoformat()}" if date_param else ""
    return {
        "status": "success",
        "message": f"Збережено/оновлено {saved_count} годинних записів погоди з OpenWeatherMap для станції #{station_id}{date_str}"
    }

@router.get("/{station_id}", response_model=List[WeatherForecastResponse])
def get_weather_forecast(
    station_id: int, 
    db: DbSessionDep,
    date_param: Optional[date] = Query(None, alias="date", description="Фільтр по даті (YYYY-MM-DD)")
):
    """Отримати збережений прогноз погоди для обраної СЕС з бази даних (з опціональним фільтром по даті)"""
    query = db.query(WeatherForecast).filter(
        WeatherForecast.station_id == station_id
    )
    if date_param is not None:
        start_dt = datetime(date_param.year, date_param.month, date_param.day, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(date_param.year, date_param.month, date_param.day, 23, 59, 59, tzinfo=timezone.utc)
        query = query.filter(
            WeatherForecast.timestamp >= start_dt,
            WeatherForecast.timestamp <= end_dt
        )
    return query.order_by(WeatherForecast.timestamp.asc()).all()
