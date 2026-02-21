from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from sqlalchemy.sql import func
from app.database import Base

class FlightOffer(Base):
    __tablename__ = "flight_offers"

    id = Column(Integer, primary_key=True, index=True)
    offer_hash = Column(String(64), unique=True, index=True, nullable=False) # Phase 2: Non-Nullable and Unique
    
    origin = Column(String(3), index=True, nullable=False)
    destination = Column(String(3), index=True, nullable=False)
    departure_date = Column(DateTime, index=True, nullable=False)
    return_date = Column(DateTime, nullable=True)
    price = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False)
    airline = Column(String(100), nullable=False)
    departure_time = Column(DateTime, nullable=False)
    arrival_time = Column(DateTime, nullable=False)
    stops = Column(Integer, nullable=False, default=0)
    duration = Column(String(20), nullable=False)
    distance_km = Column(Float, nullable=True, index=True) # Track Haversine distance for Machine Learning
    number_of_bookable_seats = Column(Integer, nullable=True)
    cabin_class = Column(String(50), nullable=True)
    fare_basis = Column(String(50), nullable=True)
    scraped_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp(), index=True, nullable=False)
    
    # Keeping indexes explicit if needed for clear Alembic generation
    __table_args__ = (
        Index('idx_origin_destination_dep', 'origin', 'destination', 'departure_date'),
        Index('idx_route_airline_created', 'origin', 'destination', 'airline', 'created_at'),
    )
