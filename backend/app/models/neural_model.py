from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from app.db.session import Base

class NeuralModel(Base):
    __tablename__ = "neural_models"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False, default="MATLAB_Baseline_v1.0")
    is_active = Column(Boolean, nullable=False, default=True)
    weights = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    station = relationship("Station", backref="neural_models")
