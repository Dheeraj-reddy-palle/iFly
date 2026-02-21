from sqlalchemy import Column, Integer, DateTime, Date
from sqlalchemy.sql import func
from app.database import Base

class CollectorState(Base):
    __tablename__ = "collector_state"

    id = Column(Integer, primary_key=True, index=True)
    last_route_offset = Column(Integer, nullable=False, default=0)
    api_calls_today = Column(Integer, nullable=False, default=0)
    last_run_date = Column(Date, nullable=False, server_default=func.current_date())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
