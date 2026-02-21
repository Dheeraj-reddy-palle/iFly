from sqlalchemy import Column, String, Boolean, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.database import Base

class RouteMaster(Base):
    __tablename__ = "routes_master"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    origin = Column(String(3), nullable=False, index=True)
    destination = Column(String(3), nullable=False, index=True)
    active = Column(Boolean, default=True, index=True)
    discovered_from_hub = Column(String(3), nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    
    __table_args__ = (
        UniqueConstraint('origin', 'destination', name='uq_origin_destination'),
    )
