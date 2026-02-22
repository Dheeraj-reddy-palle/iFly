"""
Amadeus Flight Offers provider — wraps existing AmadeusService.
"""
import asyncio
import logging
from typing import List, Dict, Any

import httpx

from data_collector.providers.base import FlightProviderInterface
from app.services.amadeus_service import AmadeusService

logger = logging.getLogger("Provider.Amadeus")


class AmadeusProvider(FlightProviderInterface):
    """Primary provider using the Amadeus Flight Offers Search API."""

    def __init__(self):
        self._service = AmadeusService()
        self._failed_attempts = 0
        self._max_consecutive_failures = 5  # After 5 consecutive 429s, mark unavailable

    @property
    def provider_name(self) -> str:
        return "amadeus"

    async def fetch_offers(
        self, origin: str, destination: str, departure_date: str
    ) -> List[Dict[str, Any]]:
        """Fetch offers via Amadeus with exponential backoff on 429."""
        base_delay = 2.0
        max_retries = 3

        for attempt in range(max_retries):
            try:
                await asyncio.sleep(1.0)  # Rate limit spacing
                offers = await self._service.search_flights(
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    adults=1,
                )
                self._failed_attempts = 0  # Reset on success
                return offers

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    self._failed_attempts += 1
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"[Amadeus] 429 Rate Limited. Backoff {delay}s "
                        f"(attempt {attempt+1}/{max_retries}, "
                        f"consecutive failures: {self._failed_attempts})"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"[Amadeus] HTTP {e.response.status_code} for {origin}-{destination}: {e}")
                    return []

            except Exception as e:
                if hasattr(e, "status_code") and e.status_code == 429:
                    self._failed_attempts += 1
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"[Amadeus] 429 via exception. Backoff {delay}s")
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"[Amadeus] Unhandled error for {origin}-{destination}: {e}")
                return []

        self._failed_attempts += 1
        logger.error(f"[Amadeus] Max retries exhausted for {origin}-{destination}")
        return []

    async def is_available(self) -> bool:
        """Available if credentials exist and we haven't hit consecutive failure threshold."""
        has_creds = bool(self._service.api_key and self._service.api_secret)
        not_exhausted = self._failed_attempts < self._max_consecutive_failures
        
        if not has_creds:
            logger.debug("[Amadeus] No credentials configured")
        if not not_exhausted:
            logger.warning(f"[Amadeus] Quota likely exhausted ({self._failed_attempts} consecutive 429s)")
        
        return has_creds and not_exhausted

    async def remaining_quota(self) -> int:
        """Estimate based on failure pattern. Amadeus doesn't expose quota via API."""
        if self._failed_attempts >= self._max_consecutive_failures:
            return 0
        return 2000  # Nominal monthly quota — can't know exact remaining
