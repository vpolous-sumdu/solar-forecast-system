from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime
from app.db.session import Base

class Station(Base):
    """
    Модель сонячної електростанції (СЕС)
    """
    __tablename__ = "stations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)           # Назва станції
    latitude = Column(Float, nullable=False)               # Широта (наприклад: 50.9077)
    longitude = Column(Float, nullable=False)              # Довгота (наприклад: 34.7981)
    installed_capacity_kw = Column(Float, nullable=False) # Встановлена потужність у кВт
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
