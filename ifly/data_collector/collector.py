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
from data_collector.routes import ROUTES, DATE_OFFSETS

# Configure logging natively for the scripts output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("DataCollector")

# Safety constraints matching user requirements
MAX_OFFERS_PER_RUN = 50000 
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
    total_combinations = len(ROUTES) * len(DATE_OFFSETS)
    current_combo = 0
    
    logger.info(f"Targeting {total_combinations} distinct route/date combinations.")

    for (origin, destination) in ROUTES:
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

    db.close()
    
    # 3. Execution Summary Output Native Requirements
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
