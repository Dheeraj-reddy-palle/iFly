import hashlib
import sys
import os
from sqlalchemy.orm import Session

# Add current path for absolute imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.flight_offer import FlightOffer

def generate_offer_hash(origin: str, destination: str, departure_date, airline: str, departure_time, price: float) -> str:
    """
    Generate SHA256 deterministic hash ensuring:
    - price rounded to 2 decimals
    - airline uppercase
    - departure_time / departure_date standard ISO format
    """
    raw_string = f"{origin}|{destination}|{departure_date.isoformat()}|{airline.upper()}|{departure_time.isoformat()}|{price:.2f}"
    return hashlib.sha256(raw_string.encode('utf-8')).hexdigest()

def run_backfill():
    db: Session = SessionLocal()
    try:
        offers = db.query(FlightOffer).filter(FlightOffer.offer_hash == None).all()
        print(f"Found {len(offers)} offers without a hash. Backfilling...")
        
        updated_count = 0
        for offer in offers:
            # Reconstruct hash logic
            offer.offer_hash = generate_offer_hash(
                origin=offer.origin,
                destination=offer.destination,
                departure_date=offer.departure_date,
                airline=offer.airline,
                departure_time=offer.departure_time,
                price=offer.price
            )
            updated_count += 1
            
        db.commit()
        print(f"Successfully backfilled {updated_count} rows.")
    except Exception as e:
        print(f"Failed to backfill: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_backfill()
