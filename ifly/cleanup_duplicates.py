import sys
import os
from sqlalchemy.orm import Session
from sqlalchemy import func

# Add current path for absolute imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.flight_offer import FlightOffer

def run_cleanup():
    db: Session = SessionLocal()
    try:
        # Find minimum IDs for each offer hash (we'll keep these)
        min_id_subq = db.query(
            FlightOffer.offer_hash,
            func.min(FlightOffer.id).label('min_id')
        ).group_by(FlightOffer.offer_hash).subquery()
        
        # Select all flight offers that have a matching offer has but are NOT the minimum ID
        duplicates = db.query(FlightOffer).outerjoin(
            min_id_subq, 
            (FlightOffer.offer_hash == min_id_subq.c.offer_hash) & 
            (FlightOffer.id == min_id_subq.c.min_id)
        ).filter(min_id_subq.c.min_id == None).all()
        
        print(f"Found {len(duplicates)} exact legacy duplicates. Deleting...")
        
        for dup in duplicates:
            db.delete(dup)
            
        db.commit()
        print("Duplicates successfully pruned.")
    except Exception as e:
        print(f"Failed to cleanup: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_cleanup()
