"""
Provider Manager — orchestrates failover across flight data providers.

Failover order:
  1. Amadeus (primary — real API pricing data)
  2. AviationStack (secondary — real schedules + estimated pricing)
  3. Synthetic (fallback — DB-backed realistic estimates)

The manager tries each provider in order. If a provider is unavailable
or returns empty results, it falls through to the next.
"""
import logging
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from data_collector.providers.amadeus_provider import AmadeusProvider
from data_collector.providers.aviationstack_provider import AviationStackProvider
from data_collector.providers.synthetic_provider import SyntheticProvider

logger = logging.getLogger("ProviderManager")


class ProviderManager:
    """
    Manages multiple flight data providers with deterministic failover.
    
    Failover chain: Amadeus → AviationStack → Synthetic
    
    Usage:
        manager = ProviderManager(db_session)
        offers = await manager.fetch_offers("DEL", "BOM", "2026-03-15")
    """

    def __init__(self, db: Session):
        self._amadeus = AmadeusProvider()
        self._aviationstack = AviationStackProvider(db)
        self._synthetic = SyntheticProvider(db)
        self._stats = {
            "amadeus_calls": 0,
            "amadeus_successes": 0,
            "aviationstack_calls": 0,
            "aviationstack_successes": 0,
            "synthetic_calls": 0,
            "synthetic_successes": 0,
            "total_offers": 0,
        }

    async def fetch_offers(
        self, origin: str, destination: str, departure_date: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch offers with automatic failover.
        
        Order: Amadeus → AviationStack → Synthetic
        """
        # 1. Try Amadeus (primary — real pricing)
        if await self._amadeus.is_available():
            self._stats["amadeus_calls"] += 1
            offers = await self._amadeus.fetch_offers(origin, destination, departure_date)
            if offers:
                self._stats["amadeus_successes"] += 1
                self._stats["total_offers"] += len(offers)
                return offers
            logger.info(f"[Failover] Amadeus empty for {origin}-{destination}. Trying AviationStack.")
        else:
            logger.info(f"[Failover] Amadeus unavailable. Trying AviationStack.")

        # 2. Try AviationStack (secondary — real schedules + estimated pricing)
        if await self._aviationstack.is_available():
            self._stats["aviationstack_calls"] += 1
            offers = await self._aviationstack.fetch_offers(origin, destination, departure_date)
            if offers:
                self._stats["aviationstack_successes"] += 1
                self._stats["total_offers"] += len(offers)
                return offers
            logger.info(f"[Failover] AviationStack empty for {origin}-{destination}. Trying synthetic.")
        else:
            logger.info(f"[Failover] AviationStack unavailable. Trying synthetic.")

        # 3. Synthetic fallback (DB-backed estimates)
        if await self._synthetic.is_available():
            self._stats["synthetic_calls"] += 1
            offers = await self._synthetic.fetch_offers(origin, destination, departure_date)
            if offers:
                self._stats["synthetic_successes"] += 1
                self._stats["total_offers"] += len(offers)
                return offers

        logger.warning(f"[Failover] All providers exhausted for {origin}-{destination} on {departure_date}")
        return []

    def get_stats(self) -> Dict[str, Any]:
        """Return collection statistics for logging."""
        return {
            **self._stats,
            "aviationstack_remaining": self._aviationstack._monthly_limit - self._aviationstack._calls_made,
            "synthetic_remaining": self._synthetic._max_daily_synthetic - self._synthetic._daily_synthetic_count,
        }

    def log_summary(self):
        """Print a summary of provider usage."""
        stats = self.get_stats()
        logger.info("=" * 50)
        logger.info("PROVIDER USAGE SUMMARY")
        logger.info("=" * 50)
        logger.info(f"  Amadeus:        {stats['amadeus_successes']}/{stats['amadeus_calls']} successful calls")
        logger.info(f"  AviationStack:  {stats['aviationstack_successes']}/{stats['aviationstack_calls']} successful calls")
        logger.info(f"  Synthetic:      {stats['synthetic_successes']}/{stats['synthetic_calls']} successful calls")
        logger.info(f"  Total offers:   {stats['total_offers']}")
        logger.info(f"  AviationStack remaining: {stats['aviationstack_remaining']}")
        logger.info(f"  Synthetic remaining:     {stats['synthetic_remaining']}")
        logger.info("=" * 50)
