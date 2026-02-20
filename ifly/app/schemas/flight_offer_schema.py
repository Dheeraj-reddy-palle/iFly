from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Optional

class FlightOfferBase(BaseModel):
    origin: str = Field(..., min_length=3, max_length=3)
    destination: str = Field(..., min_length=3, max_length=3)
    departure_date: datetime
    return_date: Optional[datetime] = None
    price: float
    currency: str
    airline: str
    departure_time: datetime
    arrival_time: datetime
    stops: int
    duration: str
    scraped_at: datetime

class FlightOfferCreate(FlightOfferBase):
    pass

class FlightOfferResponse(FlightOfferBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class FlightSearchRequest(BaseModel):
    origin: str = Field(..., min_length=3, max_length=3, description="IATA Airport Code, 3 chars uppercase.")
    destination: str = Field(..., min_length=3, max_length=3, description="IATA Airport Code, 3 chars uppercase.")
    departure_date: str = Field(..., description="YYYY-MM-DD format")
    return_date: Optional[str] = Field(None, description="YYYY-MM-DD format")
    adults: int = Field(1, ge=1, le=9)

    @field_validator("origin", "destination")
    def validate_iata(cls, v):
        if not v.isupper() or not v.isalpha():
            raise ValueError("IATA code must be exactly 3 uppercase letters.")
        return v
    
    @field_validator("departure_date", "return_date")
    def validate_dates(cls, v, info):
        if v is None:
            return v
        try:
            parsed_date = datetime.strptime(v, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")
        
        # Don't rigidly enforce 'not in the past' for departure if testing requires historical mocked dates
        # but for production Amadeus returns errors on past dates.
        
        if info.field_name == "return_date" and "departure_date" in info.data:
            dep_date_str = info.data["departure_date"]
            if dep_date_str:
                dep_date = datetime.strptime(dep_date_str, "%Y-%m-%d").date()
                if parsed_date < dep_date:
                    raise ValueError("return_date must not be earlier than departure_date")
        return v
