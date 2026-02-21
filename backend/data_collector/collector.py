import os
import math
import asyncio
import logging
from datetime import datetime, timedelta
import hashlib
from typing import List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
import httpx

from app.database import SessionLocal
from app.services.amadeus_service import AmadeusService
from app.models.flight_offer import FlightOffer
from sqlalchemy import text
from data_collector.routes import DATE_OFFSETS

# Configure logging natively for the scripts output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("DataCollector")

# Safety constraints matching user requirements
MAX_OFFERS_PER_RUN = 50000 
MAX_DAILY_API_QUOTA = 2000
RUNS_PER_DAY = 2
API_BUFFER_PERCENT = 0.10

def compute_runs_remaining(current_time: datetime, runs_per_day: int) -> int:
    hour = current_time.hour
    interval = 24 / runs_per_day
    completed_runs = int(hour // interval)
    runs_left = runs_per_day - completed_runs
    return max(1, runs_left)
MAX_RETRIES = 3

async def _fetch_with_backoff(amadeus_svc: AmadeusService, origin: str, dest: str, target_date: str) -> List[Dict[str, Any]]:
    """Execute search wrapping exponential backoff specifically targeting 429 warnings."""
    base_delay = 2.0
    
    for attempt in range(MAX_RETRIES):
        try:
            # Let the API breathe between explicit calls per loop requirements
            await asyncio.sleep(1.0)
            
            offers = await amadeus_svc.search_flights(
                origin=origin,
                destination=dest,
                departure_date=target_date,
                adults=1
            )
            return offers
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"429 Rate Limited. Backing off for {delay}s... (Attempt {attempt+1}/{MAX_RETRIES})")
                await asyncio.sleep(delay)
                continue
            else:
                # E.g. 500 downstream, or 400 bad origin
                logger.error(f"HTTP {e.response.status_code} skipping route {origin}-{dest}: {e}")
                return []
                
        except Exception as e:
            if hasattr(e, "status_code") and e.status_code == 429:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"429 Rate Limited. Backing off for {delay}s... (Attempt {attempt+1}/{MAX_RETRIES})")
                await asyncio.sleep(delay)
                continue
            logger.error(f"Unhandled exception fetching {origin}-{dest}: {e}")
            return []
            
    logger.error(f"Maximum retries exhausted for {origin}-{dest} on {target_date}.")
    return []

def _upsert_offers(db: Session, offers: List[Dict[str, Any]]) -> dict:
    """Batches insertion using ON CONFLICT DO NOTHING metrics loop."""
    if not offers:
        return {"inserted": 0, "skipped": 0}
        
    upsert_values = []
    
    try:
        for offer_data in offers:
            origin = offer_data["origin"]
            destination = offer_data["destination"]
            dep_date_str = offer_data["departure_date"].isoformat()
            airline = offer_data["airline"].upper()
            dep_time_str = offer_data["departure_time"].isoformat()
            price = round(offer_data["price"], 2)
            
            raw_hash = f"{origin}|{destination}|{dep_date_str}|{airline}|{dep_time_str}|{price:.2f}"
            offer_hash = hashlib.sha256(raw_hash.encode('utf-8')).hexdigest()
            
            offer_data["offer_hash"] = offer_hash
            upsert_values.append(offer_data)
            
        stmt = insert(FlightOffer).values(upsert_values)
        stmt = stmt.on_conflict_do_nothing(index_elements=['offer_hash'])
        
        result = db.execute(stmt)
        db.commit()
        
        inserted_count = result.rowcount
        skipped_count = len(upsert_values) - inserted_count
        
        return {"inserted": inserted_count, "skipped": skipped_count}
        
    except Exception as e:
        logger.error(f"DB insertion failure: {e}")
        db.rollback()
        return {"inserted": 0, "skipped": len(offers)}


async def main():
    logger.info("Initializing Daily iFly Collector Pipeline...")
    
    # Bypass FastAPI to access underlying layer securely natively
    db = SessionLocal()
    amadeus = AmadeusService()
    
    # Metric Trackers
    stats = {
        "total_fetched": 0,
        "total_inserted": 0,
        "total_duplicates_skipped": 0,
        "total_failures": 0
    }
    
    today = datetime.now()
    
    ROUTE_BATCH_SIZE_MAX = 50
    calls_per_route = len(DATE_OFFSETS)
    
    # 1. Fetch Total Active
    total_query = text("SELECT COUNT(*) FROM routes_master WHERE active = TRUE")
    total_routes = db.execute(total_query).scalar()
    
    if not total_routes or total_routes == 0:
        logger.warning("No active routes found in routes_master! Ensure discovery has seeded database.")
        db.close()
        return
        
    # 2. Row Lock & Fetch State Offset & Quota
    state_query = text("SELECT last_route_offset, api_calls_today, last_run_date FROM collector_state ORDER BY id ASC LIMIT 1 FOR UPDATE")
    state_row = db.execute(state_query).fetchone()
    
    current_offset = 0
    api_calls_today = 0
    
    if state_row:
        current_offset = state_row.last_route_offset or 0
        if state_row.last_run_date == today.date():
            api_calls_today = state_row.api_calls_today or 0
            
    # Calculate Quota
    remaining_calls_today = max(0, MAX_DAILY_API_QUOTA - api_calls_today)
    runs_left_today = compute_runs_remaining(today, RUNS_PER_DAY)
    usable_quota = int(remaining_calls_today * (1 - API_BUFFER_PERCENT))
    safe_calls_per_run = math.floor(usable_quota / runs_left_today)
    dynamic_batch_size = math.floor(safe_calls_per_run / calls_per_route)
    
    logger.info(f"Remaining API Quota: {remaining_calls_today}")
    logger.info(f"Runs Left Today: {runs_left_today}")
    logger.info(f"Safe Calls This Run: {safe_calls_per_run}")
    logger.info(f"Calls Per Route: {calls_per_route}")
    logger.info(f"Dynamic Batch Size: {dynamic_batch_size}")
    
    if dynamic_batch_size < 1:
        logger.warning("Insufficient quota for minimum batch. Skipping run.")
        db.rollback()
        db.close()
        return
        
    dynamic_batch_size = min(dynamic_batch_size, ROUTE_BATCH_SIZE_MAX)
    effective_batch_size = min(dynamic_batch_size, total_routes)
    
    if effective_batch_size < ROUTE_BATCH_SIZE_MAX and effective_batch_size < total_routes:
        logger.warning(f"Quota Low. Reducing batch to {effective_batch_size} routes.")
        
    logger.info(f"Effective Batch Size: {effective_batch_size}")
    
    # 3. Load Batch
    # ORDER BY id ASC is mandatory for deterministic rotation
    active_routes_query = text("""
        SELECT origin, destination 
        FROM routes_master 
        WHERE active = TRUE 
        ORDER BY id ASC
        LIMIT :limit OFFSET :offset
    """)
    active_routes = db.execute(active_routes_query, {"limit": effective_batch_size, "offset": current_offset}).fetchall()
    
    if not active_routes:
        logger.warning("Batch empty despite total count! Resetting offset to 0 safely.")
        current_offset = 0
        active_routes = db.execute(active_routes_query, {"limit": effective_batch_size, "offset": current_offset}).fetchall()
        if not active_routes:
            logger.warning("No routes fetched after reset. Terminating.")
            db.rollback()
            db.close()
            return

    actual_batch_size = len(active_routes)
    new_offset = (current_offset + actual_batch_size) % total_routes
    
    # Release Lock immediately post read allowing parallel action triggers gracefully without waiting 2 hrs
    db.commit()
    
    logger.info(f"Total Active Routes: {total_routes}")
    logger.info(f"Current Offset: {current_offset}")
    logger.info(f"Processing Routes: {current_offset + 1}-{current_offset + actual_batch_size}")
    logger.info(f"Next Offset: {new_offset}")
    logger.info(f"Effective Batch Size: {effective_batch_size}")
    
    # 3.5 Optional Quota Validation Guardrail
    max_api_calls_env = os.environ.get("MAX_API_CALLS_PER_RUN")
    if max_api_calls_env:
        max_api_calls = int(max_api_calls_env)
        expected_calls = actual_batch_size * len(DATE_OFFSETS)
        if expected_calls > max_api_calls:
            allowed = max(1, max_api_calls // len(DATE_OFFSETS))
            logger.warning(f"Expected API calls {expected_calls} exceeds MAX_API_CALLS_PER_RUN ({max_api_calls}). Reducing batch from {actual_batch_size} to {allowed}.")
            active_routes = active_routes[:allowed]
            actual_batch_size = len(active_routes)
            # Recompute target modulo explicitly isolating downstream block offsets
            new_offset = (current_offset + actual_batch_size) % total_routes
            
    total_combinations = actual_batch_size * len(DATE_OFFSETS)
    current_combo = 0
    
    logger.info(f"Targeting {total_combinations} distinct route/date combinations using {actual_batch_size} routes.")

    for row in active_routes:
        origin = row.origin
        destination = row.destination
        for offset in DATE_OFFSETS:
            current_combo += 1
            
            if stats["total_inserted"] >= MAX_OFFERS_PER_RUN:
                logger.warning(f"SAFETY CAP HIT: {MAX_OFFERS_PER_RUN} exceeded. Terminating gracefully.")
                break
                
            target_date = (today + timedelta(days=offset)).strftime("%Y-%m-%d")
            logger.info(f"[{current_combo}/{total_combinations}] Fetching: {origin} -> {destination} on {target_date}")
            
            # 1. Fetch
            offers = await _fetch_with_backoff(amadeus, origin, destination, target_date)
            
            if not offers:
                stats["total_failures"] += 1
                continue
                
            stats["total_fetched"] += len(offers)
            
            # 2. Upsert
            upsert_metrics = _upsert_offers(db, offers)
            stats["total_inserted"] += upsert_metrics["inserted"]
            stats["total_duplicates_skipped"] += upsert_metrics["skipped"]
            
            logger.info(f"    - Found: {len(offers)} | Saved: {upsert_metrics['inserted']} | Skipped: {upsert_metrics['skipped']}")

        # 4. Save Final State
        # Wrap explicit modulo rotations securely resolving API loops gracefully!
        new_api_calls_today = api_calls_today + (actual_batch_size * calls_per_route)
        update_state = text("""
            UPDATE collector_state 
            SET last_route_offset = :new_offset, 
                api_calls_today = :new_api_calls_today,
                last_run_date = CURRENT_DATE,
                updated_at = NOW() 
            WHERE id = (SELECT id FROM collector_state ORDER BY id ASC LIMIT 1)
        """)
        db.execute(update_state, {
            "new_offset": new_offset,
            "new_api_calls_today": new_api_calls_today
        })
        db.commit()
        
        logger.info(f"Next rotation offset securely set to {new_offset}")
        
    db.close()
    
    # 5. Execution Summary Output Native Requirements
    logger.info("="*40)
    logger.info("COLLECTION RUN SUMMARY")
    logger.info("="*40)
    logger.info(f"Total Offers Fetched:    {stats['total_fetched']}")
    logger.info(f"New Offers Inserted:     {stats['total_inserted']}")
    logger.info(f"Duplicates Skipped:      {stats['total_duplicates_skipped']}")
    logger.info(f"Failed Route Queries:    {stats['total_failures']}")
    logger.info("="*40)

if __name__ == "__main__":
    asyncio.run(main())
