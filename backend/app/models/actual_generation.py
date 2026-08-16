from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.db.session import Base

class ActualGeneration(Base):
    """
    Модель фактичної генерації сонячної електростанції (з PVOutput)
    """
    __tablename__ = "actual_generations"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    actual_power_watts = Column(Float, nullable=False, default=0.0)
    actual_power_kw = Column(Float, nullable=False, default=0.0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    station = relationship("Station", backref="actual_generations")

    __table_args__ = (
        UniqueConstraint("station_id", "timestamp", name="uq_station_actual_timestamp"),
    )
