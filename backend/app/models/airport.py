from sqlalchemy import Column, String, Float
from app.database import Base

class Airport(Base):
    __tablename__ = "airports"

    iata_code = Column(String(3), primary_key=True, index=True) # PK acts as automatic index
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    country = Column(String(100), nullable=True)
