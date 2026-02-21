from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from typing import List
import logging
import hashlib

from app.database import get_db
from app.schemas.flight_offer_schema import FlightSearchRequest, FlightOfferResponse
from app.services.amadeus_service import AmadeusService
from app.models.flight_offer import FlightOffer

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/search",
    tags=["flights"]
)

# Initialize service once, it maintains its own state (token caching)
amadeus_svc = AmadeusService()

@router.post("", response_model=List[FlightOfferResponse])
async def search_flights(request: FlightSearchRequest, db: Session = Depends(get_db)):
    """
    Search for flights via Amadeus and cache the normalized results in the local PostgreSQL database.
    Strict route logic matching to Pydantic constraints.
    """
    
    # 1. Fetch from Amadeus Service
    try:
        offers = await amadeus_svc.search_flights(
            origin=request.origin,
            destination=request.destination,
            departure_date=request.departure_date,
            return_date=request.return_date,
            adults=request.adults
        )
    except Exception as e:
        # Re-raise HTTPExceptions thrown by the service layer directly, log others
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Unexpected error calling Amadeus service: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during flight search.")

    # 2. Store offers in database
    inserted_hashes = []
    
    # Use nested transaction logic for safety, rollback on failure to prevent partial commits
    try:
        # Build deterministic hashes and batch insertion mappings
        upsert_values = []
        for offer_data in offers:
            # Enforce data normalization before hashing
            origin = offer_data["origin"]
            destination = offer_data["destination"]
            dep_date_str = offer_data["departure_date"].isoformat()
            airline = offer_data["airline"].upper() # Enforce upper
            dep_time_str = offer_data["departure_time"].isoformat()
            price = round(offer_data["price"], 2) # Ensure 2 decimal fixed floating mapping
            
            raw_hash = f"{origin}|{destination}|{dep_date_str}|{airline}|{dep_time_str}|{price:.2f}"
            offer_hash = hashlib.sha256(raw_hash.encode('utf-8')).hexdigest()
            
            offer_data["offer_hash"] = offer_hash
            upsert_values.append(offer_data)
            inserted_hashes.append(offer_hash)
            
        if upsert_values:
            stmt = insert(FlightOffer).values(upsert_values)
            stmt = stmt.on_conflict_do_nothing(index_elements=['offer_hash'])
            db.execute(stmt)
            db.commit()
            
    except Exception as e:
        logger.error(f"Database insertion failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save flight offers.")

    # 3. Return results
    # Fetch exactly the rows corresponding to our batch (including pre-existing duplicates we skipped insertion on!)
    if not inserted_hashes:
        return []
        
    db_offers = db.query(FlightOffer).filter(FlightOffer.offer_hash.in_(inserted_hashes)).all()
    return db_offers
