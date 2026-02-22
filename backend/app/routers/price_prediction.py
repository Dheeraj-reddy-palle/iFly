from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
import joblib
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
import pytz
import asyncio
import logging

logger = logging.getLogger(__name__)

from app.models.model_registry import ModelRegistry
from app.database import SessionLocal

router = APIRouter(prefix="/predict-price", tags=["Prediction"])

class PricePredictionRequest(BaseModel):
    origin: str
    destination: str
    departure_date: str
    airline: str
    stops: int

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
metadata_path = os.path.join(BASE_DIR, "ml", "model_metadata.json")
residual_stats_path = os.path.join(BASE_DIR, "ml", "residual_stats.json")

model = None
metadata = None
residual_stats = None
current_deployed_version = None

def load_deployed_model():
    global model, metadata, residual_stats, current_deployed_version
    
    db = SessionLocal()
    try:
        deployed_reg = db.query(ModelRegistry).filter(ModelRegistry.deployed == True).first()
        if not deployed_reg:
            logger.warning("No deployed model found in model_registry. Server will start without prediction capability.")
            return
            
        model_path = deployed_reg.file_path
        if not os.path.exists(model_path):
            # Fallback: try resolving relative to BASE_DIR/models/ using just the filename
            filename = os.path.basename(model_path)
            model_path = os.path.join(BASE_DIR, "models", filename)
            logger.info(f"Original path not found, trying relative: {model_path}")
        
        # If .pkl doesn't exist, try decompressing .pkl.gz
        if not os.path.exists(model_path) and os.path.exists(model_path + ".gz"):
            import gzip
            import shutil
            logger.info(f"Decompressing {model_path}.gz ...")
            with gzip.open(model_path + ".gz", 'rb') as f_in:
                with open(model_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            logger.info(f"Decompressed model to {model_path}")
        
        if not os.path.exists(model_path):
            logger.warning(f"Deployed model file missing at path: {model_path}. Skipping load.")
            return
            
        new_model = joblib.load(model_path)
        
        # Load auxiliary stats
        new_metadata = None
        new_residual_stats = None
        
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                new_metadata = json.load(f)
        else:
            logger.warning("Missing model_metadata.json. Skipping load.")
            return
            
        if os.path.exists(residual_stats_path):
            with open(residual_stats_path, 'r') as f:
                new_residual_stats = json.load(f)
        else:
            logger.warning("Missing residual_stats.json. Skipping load.")
            return
            
        # Atomic swap
        model = new_model
        metadata = new_metadata
        residual_stats = new_residual_stats
        current_deployed_version = deployed_reg.model_version
        
        logger.info(f"Successfully loaded deployed model instance: {current_deployed_version}")
        
    finally:
        db.close()

async def poll_model_updates():
    while True:
        try:
            await asyncio.sleep(300)
            db = SessionLocal()
            try:
                deployed_reg = db.query(ModelRegistry).filter(ModelRegistry.deployed == True).first()
                if deployed_reg and deployed_reg.model_version != current_deployed_version:
                    logger.info(f"New model version detected: {deployed_reg.model_version}. Hot reloading...")
                    load_deployed_model()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error in model polling loop: {e}")

@router.on_event("startup")
async def startup_event():
    logger.info("Initializing ML Prediction Router...")
    try:
        load_deployed_model()
    except Exception as e:
        logger.error(f"Model loading failed during startup: {e}. Server will start without prediction.")
    asyncio.create_task(poll_model_updates())

@router.get("/model-info")
def get_model_info(db: Session = Depends(get_db)):
    deployed = db.query(ModelRegistry).filter(ModelRegistry.deployed == True).first()
    if not deployed:
        return {"status": "No deployed model"}
        
    return {
        "model_version": deployed.model_version,
        "trained_at": deployed.trained_at.isoformat(),
        "test_r2": deployed.test_r2,
        "test_mae": deployed.test_mae,
        "status": "deployed" if deployed.deployed else "candidate"
    }

@router.post("/model-rollback/{model_version}")
def rollback_model(model_version: str, db: Session = Depends(get_db)):
    target = db.query(ModelRegistry).filter(ModelRegistry.model_version == model_version).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target model version not found.")
        
    current = db.query(ModelRegistry).filter(ModelRegistry.deployed == True).first()
    
    # Enable rollback safely swapping deployment flags
    if current:
        current.deployed = False
        db.add(current)
        
    target.deployed = True
    target.is_candidate = False
    db.add(target)
    db.commit()
    
    # Force memory reload cleanly locally!
    try:
        load_deployed_model()
    except Exception as e:
        # Prevent partial crashes breaking instance
        raise HTTPException(status_code=500, detail=f"Rollback database successful, but memory reload failed: {str(e)}")
        
    return {"message": f"Successfully rolled back and deployed {model_version}"}

@router.get("/model-history")
def get_model_history(db: Session = Depends(get_db)):
    # Mandatory: Sort by trained_at ascending for React charts chronological integrity
    history = db.query(ModelRegistry).order_by(ModelRegistry.trained_at.asc()).limit(20).all()
    return [{
        "version": m.model_version,
        "train_r2": float(m.train_r2) if m.train_r2 else None,
        "test_r2": float(m.test_r2) if m.test_r2 else None,
        "mae": float(m.test_mae) if m.test_mae else None,
        "rmse": float(m.test_rmse) if m.test_rmse else None,
        "deployed": m.deployed,
        "is_candidate": m.is_candidate,
        "trained_at": m.trained_at.isoformat()
    } for m in history]

@router.post("")
def predict_price(req: PricePredictionRequest, db: Session = Depends(get_db)):
    if model is None or metadata is None or residual_stats is None:
        raise HTTPException(status_code=503, detail="Model uninitialized or missing dependencies.")
        
    created_at = datetime.now(pytz.UTC)
    try:
        departure_date = pd.to_datetime(req.departure_date, utc=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid departure_date format. Use YYYY-MM-DD.")
    
    route_key = f"{req.origin}-{req.destination}"
    airline_route = f"{req.airline}-{route_key}"
    
    days_until_departure = max((departure_date - created_at).days, 0)
    month = departure_date.month
    weekday = departure_date.weekday()
    
    # Extract live historical bounds mimicking StatefulFeatureExtractor locally 
    query_str = """
        SELECT price, created_at, airline 
        FROM flight_offers 
        WHERE origin = :origin AND destination = :destination 
        AND created_at >= NOW() - INTERVAL '30 days'
        AND created_at < NOW()
        ORDER BY created_at ASC
    """
    history_res = db.execute(text(query_str), {"origin": req.origin, "destination": req.destination}).fetchall()
    history_df = pd.DataFrame([dict(row._mapping) for row in history_res])
    
    prices_30d = []
    prices_7d = []
    airline_prices_30d = []
    airline_prices_7d = []
    
    now = pd.Timestamp.utcnow()
    
    if not history_df.empty:
        history_df['created_at'] = pd.to_datetime(history_df['created_at'], utc=True)
        for _, row in history_df.iterrows():
            prices_30d.append(row['price'])
            if row['airline'] == req.airline:
                airline_prices_30d.append(row['price'])
                
            if row['created_at'] >= now - pd.Timedelta(days=7):
                prices_7d.append(row['price'])
                if row['airline'] == req.airline:
                    airline_prices_7d.append(row['price'])
                
    offer_count_7d = len(prices_7d)
    airline_route_offer_count_7d = len(airline_prices_7d)
                
    if len(prices_30d) > 0:
        route_rolling_mean_30d = float(np.mean(prices_30d))
        route_rolling_std_30d = float(np.std(prices_30d))
        if route_rolling_std_30d == 0: route_rolling_std_30d = 1.0
    else:
        route_rolling_mean_30d = 8000.0 # safe fallback mean
        route_rolling_std_30d = 1.0
        
    if len(prices_7d) > 0:
        route_mean_7d = float(np.mean(prices_7d))
    else:
        route_mean_7d = route_rolling_mean_30d
        
    if len(airline_prices_30d) > 0:
        airline_route_rolling_mean_30d = float(np.mean(airline_prices_30d))
        airline_route_rolling_std_30d = float(np.std(airline_prices_30d))
        if airline_route_rolling_std_30d == 0: airline_route_rolling_std_30d = 1.0
    else:
        airline_route_rolling_mean_30d = route_rolling_mean_30d
        airline_route_rolling_std_30d = route_rolling_std_30d
        
    airline_route_mean_price = airline_route_rolling_mean_30d

    if len(airline_prices_7d) > 0:
        airline_route_mean_7d = float(np.mean(airline_prices_7d))
        airline_std_7d = float(np.std(airline_prices_7d))
        airline_route_volatility_7d = airline_std_7d / airline_route_mean_7d if airline_route_mean_7d > 0 else 1e-6
    else:
        airline_route_mean_7d = airline_route_rolling_mean_30d
        airline_route_volatility_7d = airline_route_rolling_std_30d / airline_route_rolling_mean_30d if airline_route_rolling_mean_30d > 0 else 1e-6
        
    route_price_momentum = route_mean_7d / route_rolling_mean_30d if route_rolling_mean_30d > 0 else 1.0
    route_volatility_index = route_rolling_std_30d / route_rolling_mean_30d if route_rolling_mean_30d > 0 else 1e-6
    
    if route_mean_7d > 0:
        airline_price_relative_to_route_mean = airline_route_mean_7d / route_mean_7d
    else:
        airline_price_relative_to_route_mean = 1.0

    
    # Distance and duration query explicitly
    dur_query = "SELECT distance_km, duration FROM flight_offers WHERE origin = :origin AND destination = :destination LIMIT 1"
    dur_res = db.execute(text(dur_query), {"origin": req.origin, "destination": req.destination}).fetchall()
    dur_df = pd.DataFrame([dict(row._mapping) for row in dur_res])
    
    distance_km = 1000.0
    duration_minutes = 120
    if not dur_df.empty:
        distance_km = float(dur_df.iloc[0]['distance_km']) if pd.notnull(dur_df.iloc[0]['distance_km']) else 1000.0
        import re
        dur_str = str(dur_df.iloc[0]['duration']).replace('PT', '')
        h_match = re.search(r'(\d+)H', dur_str)
        m_match = re.search(r'(\d+)M', dur_str)
        h = int(h_match.group(1)) if h_match else 0
        m = int(m_match.group(1)) if m_match else 0
        duration_minutes = h * 60 + m
        
    departure_hour_bucket = 1 # noon proxy for inference
    
    input_dict = {
        'distance_km': distance_km,
        'stops': req.stops,
        'month': month,
        'weekday': weekday,
        'departure_hour_bucket': departure_hour_bucket,
        'duration_minutes': duration_minutes,
        'days_until_departure': days_until_departure,
        'route_rolling_mean_30d': route_rolling_mean_30d,
        'route_rolling_std_30d': route_rolling_std_30d,
        'airline_route_mean_price': airline_route_mean_price,
        'route_offer_count_7d': offer_count_7d,
        'route_mean_7d': route_mean_7d,
        'route_price_momentum': route_price_momentum,
        'route_volatility_index': route_volatility_index,
        'airline_route_mean_7d': airline_route_mean_7d,
        'airline_route_volatility_7d': airline_route_volatility_7d,
        'airline_route_offer_count_7d': airline_route_offer_count_7d,
        'airline_price_relative_to_route_mean': airline_price_relative_to_route_mean,
        'airline_freq': 0.1, # generalized safe bounding fallback
        'route_key_freq': 0.1 # generalized safe bounding fallback
    }
    
    features_list = metadata["features"]
    input_df = pd.DataFrame([input_dict])[features_list]
    
    pred_log = model.predict(input_df)[0]
    
    # Do NOT apply expm1. The model was dumped BEFORE log1p training became active!
    pred_price = float(pred_log)
    
    # Numeric safety guards
    if not np.isfinite(pred_price):
        logger.error(f"Non-finite prediction detected for route {route_key}: {pred_price}")
        raise HTTPException(status_code=500, detail="Non-finite prediction detected")

    if pred_price < 0:
        pred_price = abs(pred_price)

    if pred_price > 200000:
        logger.warning(f"Abnormal prediction for route {route_key}: {pred_price}")
    
    global_std = residual_stats.get("global_residual_std", 500.0)
    route_std = residual_stats.get(route_key, global_std)
    
    lower_bound = max(0.0, pred_price - route_std)
    upper_bound = pred_price + route_std
    
    return {
        "predicted_price_eur": round(pred_price, 2),
        "confidence_interval_eur": {
            "lower": round(lower_bound, 2),
            "upper": round(upper_bound, 2)
        },
        "confidence_level": "approximately 68%",
        "base_currency": "EUR",
        "model_version": current_deployed_version or "unknown",
        "prediction_timestamp": created_at.isoformat()
    }
