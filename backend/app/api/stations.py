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
    """Синхронізувати/Оновити список дефолтних еталонних станцій з еталону"""
    from seed_stations import DEFAULT_STATIONS
    count = 0
    for item in DEFAULT_STATIONS:
        station = db.query(Station).filter(Station.id == item["id"]).first()
        if not station:
            station = Station(
                id=item["id"],
                name=item["name"],
                latitude=item["latitude"],
                longitude=item["longitude"],
                installed_capacity_kw=item["installed_capacity_kw"]
            )
            db.add(station)
        else:
            station.name = item["name"]
            station.latitude = item["latitude"]
            station.longitude = item["longitude"]
            station.installed_capacity_kw = item["installed_capacity_kw"]
        count += 1
    db.commit()
    return {"status": "success", "message": f"Синхронізовано {count} станцій"}

