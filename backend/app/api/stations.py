from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.station import Station
from app.schemas.station import StationCreate, StationResponse

# Використовуємо Annotated для залежностей сесій СУБД

DbSessionDep = Annotated[Session, Depends(get_db)]

router = APIRouter(
    prefix="/stations",
    tags=["Сонячні Станції (Stations)"]
)

@router.get("/", response_model=List[StationResponse])
def get_stations(db: DbSessionDep):
    """Отримати список усіх зареєстрованих сонячних електростанцій"""
    stations = db.query(Station).all()
    return stations

@router.post("/sync", status_code=status.HTTP_200_OK)
def sync_default_stations(db: DbSessionDep):
    """Синхронізувати/Оновити список дефолтних еталонних станцій з PVOutput"""
    from seed_stations import seed_and_sync_stations
    stats = seed_and_sync_stations()
    total = stats.get("total", 0)
    return {"status": "success", "message": f"Синхронізацію {total} станцій з PVOutput успішно виконано"}



