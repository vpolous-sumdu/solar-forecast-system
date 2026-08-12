from sqlalchemy import Column, Integer, Float, DateTime, String, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.db.session import Base

class WeatherForecast(Base):
    __tablename__ = "weather_forecasts"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    temperature = Column(Float, nullable=False)
    cloud_cover = Column(Float, nullable=False)
    pressure = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    wind_speed = Column(Float, nullable=False)
    source = Column(String(50), nullable=False, server_default="Open-Meteo")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    station = relationship("Station", backref="weather_forecasts")

    __table_args__ = (
        UniqueConstraint("station_id", "timestamp", name="uq_station_weather_timestamp"),
    )
