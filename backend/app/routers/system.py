from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from app.database import get_db
from app.models.flight_offer import FlightOffer
from app.models.model_registry import ModelRegistry

router = APIRouter(prefix="/system-health", tags=["System"])

@router.get("")
def get_system_health(db: Session = Depends(get_db)):
    total_records = db.query(func.count(FlightOffer.id)).scalar() or 0
    total_routes = db.query(func.count(distinct(FlightOffer.origin + '-' + FlightOffer.destination))).scalar() or 0
    total_airlines = db.query(func.count(distinct(FlightOffer.airline))).scalar() or 0
    
    deployed_model = db.query(ModelRegistry).filter(ModelRegistry.deployed == True).first()
    
    return {
        "total_records": total_records,
        "total_routes": total_routes,
        "total_airlines": total_airlines,
        "deployed_model_version": deployed_model.model_version if deployed_model else None,
        "last_retrain_timestamp": deployed_model.trained_at.isoformat() if deployed_model else None
    }
