from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.actual_generation_service import get_or_sync_actual_generation
from app.services.comparison_service import (
    compare_forecast_and_actual_for_date,
    get_available_comparison_dates
)

DbSessionDep = Annotated[Session, Depends(get_db)]

router = APIRouter(
    prefix="/comparison",
    tags=["Порівняння Генерації (Comparison)"]
)


@router.get("/{station_id}", status_code=status.HTTP_200_OK)
def get_comparison(
        station_id: int,
        db: DbSessionDep,
        date_str: Optional[str] = Query(None, alias="date", description="Дата у форматі YYYY-MM-DD"),
        weather_source: str = Query("OpenWeatherMap", description="Джерело погоди (OpenWeatherMap / Open-Meteo)"),
        model_id: Optional[int] = Query(None, description="ID моделі нейромережі"),
        force_sync: bool = Query(False, description="Примусово оновити факт з PVOutput API")
):
    """
    Отримати порівняння прогнозованої та фактичної генерації за вказану дату та станцію.
    """
    from datetime import timedelta
    if date_str:
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            target_date = date.today() - timedelta(days=1)
    else:
        # За замовчуванням беремо попередній день (вчора)
        target_date = date.today() - timedelta(days=1)

    result = compare_forecast_and_actual_for_date(
        db=db,
        station_id=station_id,
        target_date=target_date,
        weather_source=weather_source,
        model_id=model_id,
        force_sync_actual=force_sync
    )
    return result


@router.get("/{station_id}/dates", status_code=status.HTTP_200_OK)
def get_dates(
        station_id: int,
        db: DbSessionDep
):
    """
    Отримати список доступних дат для порівняння станції
    """
    dates = get_available_comparison_dates(db, station_id)
    return {
        "station_id": station_id,
        "count": len(dates),
        "dates": dates
    }


@router.post("/sync-actual/{station_id}", status_code=status.HTTP_200_OK)
def sync_actual(
        station_id: int,
        db: DbSessionDep,
        date_str: str = Query(..., alias="date", description="Дата у форматі YYYY-MM-DD")
):
    """
    Примусово синхронізувати та зберегти факт із PVOutput API за вказану дату
    """
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        target_date = date.today()

    records = get_or_sync_actual_generation(db, station_id, target_date, force_sync=True)
    return {
        "status": "success",
        "station_id": station_id,
        "date": target_date.isoformat(),
        "synced_records": len(records),
        "total_actual_kwh": round(sum(r.actual_power_kw for r in records), 2)
    }
