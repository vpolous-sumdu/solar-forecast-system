from datetime import date
from typing import Annotated, Optional
import os

from fastapi import APIRouter, Depends, Query, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.neural_model import NeuralModel
from app.services.forecast_service import (
    generate_power_forecast_for_station,
    get_saved_forecast_for_station,
    run_batch_forecast_for_all_stations
)

DbSessionDep = Annotated[Session, Depends(get_db)]

router = APIRouter(
    prefix="/forecast",
    tags=["Прогноз Генерації (Forecast)"]
)

@router.get("/models/{station_id}", status_code=status.HTTP_200_OK)
def get_station_neural_models(station_id: int, db: DbSessionDep):
    """Отримати список доступних нейромережевих моделей для станції з бази даних Neon"""
    models = db.query(NeuralModel).filter(
        NeuralModel.station_id == station_id
    ).order_by(NeuralModel.id.asc()).all()
    
    return [
        {
            "id": m.id,
            "station_id": m.station_id,
            "name": m.name,
            "code": m.code,
            "created_at": m.created_at
        }
        for m in models
    ]



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
    """Розрахувати прогноз генерації за обраним джерелом погоди, датою та моделлю для однієї станції"""
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


@router.post("/generate-all", status_code=status.HTTP_200_OK)
def generate_all_stations_forecast(
        db: DbSessionDep,
        weather_source: str = "ALL",
        model_id: Optional[int] = None,
        date_param: Optional[date] = Query(None, alias="date", description="Дата для розрахунку прогнозу (YYYY-MM-DD)")
):
    """
    Пакетний розрахунок прогнозу генерації для ВСІХ зареєстрованих СЕС на вказану дату.
    За замовчуванням (weather_source="ALL") розраховує одразу для OpenWeatherMap та Open-Meteo.
    """
    report = run_batch_forecast_for_all_stations(
        db=db,
        target_date=date_param,
        weather_source=weather_source,
        model_id=model_id
    )
    return report


@router.post("/cron/daily-batch", status_code=status.HTTP_200_OK)
def cron_daily_batch_forecast(
        db: DbSessionDep,
        x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret"),
        weather_source: str = Query("ALL", description="Джерело погоди (ALL / OpenWeatherMap / Open-Meteo)"),
        model_id: Optional[int] = Query(None, description="ID моделі нейромережі"),
        date_param: Optional[date] = Query(None, alias="date", description="Опціональна дата (за замовчуванням завтра)")
):
    """
    Спеціальний захищений ендпоінт для GitHub Actions / Vercel Cron.
    Автоматично розраховує погодинний прогноз генерації на наступний день для всіх 12 станцій для обох джерел погоди.
    """
    expected_secret = os.getenv("CRON_SECRET")
    if expected_secret and x_cron_secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недійсний або відсутній X-Cron-Secret токен авторизації."
        )

    report = run_batch_forecast_for_all_stations(
        db=db,
        target_date=date_param,
        weather_source=weather_source,
        model_id=model_id
    )
    return report
