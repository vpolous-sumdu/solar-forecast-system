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

    # Астрономічні та сонячні поля 1-в-1 з еталоном (unit2.py / unit4.py)
    st_s = Column(Integer, nullable=False, default=0)              # Ніч (0), Сутінки (1), День (2)
    h_svetl = Column(Float, nullable=False, default=0.0)           # Частка інсоляції інтервалу (0.0 ... 1.0)
    azimuth = Column(Float, nullable=False, default=0.0)           # Азимут сонця (градуси)
    elevation = Column(Float, nullable=False, default=0.0)         # Висота сонця над горизонтом (градуси)
    day_of_week = Column(Integer, nullable=False, default=1)       # День тижня (1-7)
    ww = Column(Float, nullable=False, default=0.0)                # Код погодного явища WMO
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    station = relationship("Station", backref="weather_forecasts")

    __table_args__ = (
        UniqueConstraint("station_id", "source", "timestamp", name="uq_station_source_weather_timestamp"),
    )

