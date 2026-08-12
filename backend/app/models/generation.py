from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.db.session import Base

class GenerationForecast(Base):
    __tablename__ = "generation_forecasts"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True)
    model_id = Column(Integer, ForeignKey("neural_models.id", ondelete="SET NULL"), nullable=True, index=True)
    
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    predicted_power_kw = Column(Float, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    station = relationship("Station", backref="generation_forecasts")
    model = relationship("NeuralModel", backref="generation_forecasts")

    __table_args__ = (
        UniqueConstraint("station_id", "timestamp", name="uq_station_generation_timestamp"),
    )
