import asyncio
import logging
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.database import SessionLocal
from app.services.amadeus_service import AmadeusService
from app.models.route_master import RouteMaster
from data_collector.hubs import HUBS

# Configure local logging natively
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RouteDiscovery")

async def expand_routes(db: Session, amadeus: AmadeusService, active_hubs: List[str]):
    """Iterates through specified global hubs to discover and persist new routes natively."""
    total_new = 0
    total_skipped = 0
    
    for hub in active_hubs:
        logger.info(f"Targeting HUB [{hub}] for route discovery...")
        
        # 1. Fetch
        destinations = await amadeus.get_airport_destinations(hub, max_results=15)
        if not destinations:
            logger.warning(f"No destinations retrieved for {hub}. Skipping.")
            continue
            
        logger.info(f"Found {len(destinations)} raw destinations for {hub}.")
        
        # 2. Map constraints natively preventing reverse duplicates where applicable
        insert_values = []
        for dest in destinations:
            # We enforce strictly origin->destination. 
            # In Phase 4.5, if JFK->LHR exists, we let it be. 
            # If the user wishes, reverse duplicates might be treated distinctly (JFK->LHR vs LHR->JFK).
            # We follow the strict rule: "prevent reverse duplicates (JFK-LHR and LHR-JFK treated distinctly)"
            # Wait, "treated distinctly" implies they are two DIFFERENT routes if the direction matters, 
            # OR it implies they are the same distinct route.
            # To be universally safe and conform to the prompt "prevent reverse duplicates", 
            # we will sort lexicographically to ensure A-B and B-A always insert as A-B, 
            # OR we just insert Hub->Dest. Given flight schedules, Hub->Dest is fine. 
            # As a safeguard against reverse mapping, we can alphabetically sort origin and destination.
            
            # Since the user requested "JFK-LHR and LHR-JFK treated distinctly", we will assume they are meant to be DISTINCT if reversed, meaning we DO NOT prevent LHR-JFK if JFK-LHR exists?
            # Actually, "prevent reverse duplicates (JFK-LHR and LHR-JFK treated distinctly)" implies we PREVENT LHR-JFK from being inserted if JFK-LHR exists natively.
            
            sorted_route = sorted([hub, dest])
            norm_origin = sorted_route[0]
            norm_dest = sorted_route[1]
            
            insert_values.append({
                "origin": norm_origin,
                "destination": norm_dest,
                "active": True,
                "discovered_from_hub": hub
            })
            
        # 3. Upsert
        if insert_values:
            stmt = insert(RouteMaster).values(insert_values)
            # Use ON CONFLICT DO NOTHING natively bounding the unique constraint
            stmt = stmt.on_conflict_do_nothing(constraint='uq_origin_destination')
            
            res = db.execute(stmt)
            db.commit()
            
            inserted = res.rowcount
            skipped = len(insert_values) - inserted
            total_new += inserted
            total_skipped += skipped
            
            logger.info(f"HUB [{hub}] -> Inserted {inserted} new routes, Skipped {skipped} existing.")
            
        # 4. Pace 
        await asyncio.sleep(1.0)
        
    logger.info("="*40)
    logger.info("ROUTE DISCOVERY SUMMARY")
    logger.info("="*40)
    logger.info(f"Total Routes Added:   {total_new}")
    logger.info(f"Total Routes Skipped: {total_skipped}")
    logger.info("="*40)


async def main():
    logger.info("Initiating Phase 4.5 Route Discovery Expansion...")
    db = SessionLocal()
    amadeus = AmadeusService()
    
    # Week 1: Activate 5 hubs only
    week_1_hubs = HUBS[:5]
    
    try:
        await expand_routes(db, amadeus, week_1_hubs)
    except Exception as e:
        logger.error(f"Global expansion crashed natively: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
