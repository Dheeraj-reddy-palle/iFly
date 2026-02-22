"""
AviationStack Flight Provider — secondary real-data source.

AviationStack's free tier (500 calls/month) provides real flight schedules
(routes, airlines, times) but NOT pricing. This provider fetches real
schedule data and enriches it with historical price estimates from the DB.

This is a hybrid approach:
  - Flight existence + timing = REAL (from AviationStack API)
  - Price estimate = HISTORICAL (from DB route statistics)
"""
import os
import logging
import random
from datetime import datetime
from typing import List, Dict, Any, Optional

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import text

from data_collector.providers.base import FlightProviderInterface

logger = logging.getLogger("Provider.AviationStack")

AVIATIONSTACK_BASE_URL = "http://api.aviationstack.com/v1"


class AviationStackProvider(FlightProviderInterface):
    """
    Secondary provider using AviationStack Flights API.
    
    Free tier: 500 calls/month, HTTP only (no HTTPS), real-time flights endpoint.
    Provides real flight schedule data; prices are estimated from DB history.
    """

    def __init__(self, db: Session):
        self._api_key = os.environ.get("AVIATIONSTACK_API_KEY", "")
        self._db = db
        self._calls_made = 0
        self._monthly_limit = 100
        self._route_price_cache: dict = {}

    @property
    def provider_name(self) -> str:
        return "aviationstack"

    async def fetch_offers(
        self, origin: str, destination: str, departure_date: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch real flight schedules from AviationStack and enrich with
        historical price estimates from the database.
        """
        if not await self.is_available():
            return []

        try:
            # AviationStack /flights endpoint
            params = {
                "access_key": self._api_key,
                "dep_iata": origin,
                "arr_iata": destination,
                "flight_status": "scheduled",
                "limit": 20,
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{AVIATIONSTACK_BASE_URL}/flights",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

            self._calls_made += 1

            if "error" in data:
                logger.error(f"[AviationStack] API error: {data['error']}")
                return []

            flights = data.get("data", [])
            if not flights:
                logger.info(f"[AviationStack] No flights found for {origin}-{destination}")
                return []

            # Get historical price stats for this route
            price_stats = self._get_route_price_stats(origin, destination)

            # Normalize to our schema
            offers = []
            for flight in flights:
                offer = self._normalize_flight(flight, origin, destination, departure_date, price_stats)
                if offer:
                    offers.append(offer)

            logger.info(f"[AviationStack] Found {len(offers)} flights for {origin}-{destination}")
            return offers

        except httpx.HTTPStatusError as e:
            logger.error(f"[AviationStack] HTTP {e.response.status_code} for {origin}-{destination}")
            return []
        except Exception as e:
            logger.error(f"[AviationStack] Error fetching {origin}-{destination}: {e}")
            return []

    async def is_available(self) -> bool:
        """Available if API key is set and monthly limit not exceeded."""
        has_key = bool(self._api_key)
        within_limit = self._calls_made < self._monthly_limit

        if not has_key:
            logger.debug("[AviationStack] No API key configured")
        if not within_limit:
            logger.warning(f"[AviationStack] Monthly limit reached ({self._calls_made}/{self._monthly_limit})")

        return has_key and within_limit

    async def remaining_quota(self) -> int:
        """Remaining API calls this month."""
        return max(0, self._monthly_limit - self._calls_made)

    def _get_route_price_stats(self, origin: str, destination: str) -> Dict:
        """Fetch historical price statistics for price estimation."""
        route_key = f"{origin}-{destination}"

        if route_key in self._route_price_cache:
            return self._route_price_cache[route_key]

        try:
            query = text("""
                SELECT 
                    AVG(price) as mean_price,
                    STDDEV(price) as std_price,
                    MIN(price) as min_price,
                    MAX(price) as max_price,
                    AVG(distance_km) as avg_distance
                FROM flight_offers
                WHERE origin = :origin AND destination = :dest
                  AND price > 0
                  AND provider_name = 'amadeus'
            """)
            row = self._db.execute(query, {"origin": origin, "dest": destination}).fetchone()

            if row and row.mean_price:
                stats = {
                    "mean": float(row.mean_price),
                    "std": float(row.std_price) if row.std_price else float(row.mean_price) * 0.2,
                    "min": float(row.min_price),
                    "max": float(row.max_price),
                    "distance_km": float(row.avg_distance) if row.avg_distance else None,
                }
            else:
                # No historical data — use conservative defaults
                stats = {"mean": 300.0, "std": 75.0, "min": 50.0, "max": 1200.0, "distance_km": None}

            self._route_price_cache[route_key] = stats
            return stats

        except Exception as e:
            logger.error(f"[AviationStack] DB stats query failed for {route_key}: {e}")
            return {"mean": 300.0, "std": 75.0, "min": 50.0, "max": 1200.0, "distance_km": None}

    def _normalize_flight(
        self,
        flight: Dict,
        origin: str,
        destination: str,
        departure_date: str,
        price_stats: Dict,
    ) -> Optional[Dict[str, Any]]:
        """Normalize AviationStack flight data to our schema."""
        try:
            departure = flight.get("departure", {})
            arrival = flight.get("arrival", {})
            airline_info = flight.get("airline", {})

            # Parse times
            dep_time_str = departure.get("scheduled") or departure.get("estimated")
            arr_time_str = arrival.get("scheduled") or arrival.get("estimated")

            if not dep_time_str or not arr_time_str:
                return None

            departure_time = datetime.fromisoformat(dep_time_str.replace("Z", "+00:00").replace("+00:00", ""))
            arrival_time = datetime.fromisoformat(arr_time_str.replace("Z", "+00:00").replace("+00:00", ""))

            # Duration
            duration_seconds = (arrival_time - departure_time).total_seconds()
            if duration_seconds <= 0:
                return None
            duration_minutes = int(duration_seconds / 60)
            duration_iso = f"PT{duration_minutes // 60}H{duration_minutes % 60}M"

            # Airline name
            airline_name = airline_info.get("name", "Unknown Airline")

            # Price estimation from historical data
            estimated_price = random.gauss(price_stats["mean"], price_stats["std"])
            estimated_price = max(price_stats["min"] * 0.8, min(price_stats["max"] * 1.2, estimated_price))
            estimated_price = round(max(10.0, estimated_price), 2)

            return {
                "origin": departure.get("iata", origin),
                "destination": arrival.get("iata", destination),
                "departure_date": departure_time,
                "return_date": None,
                "price": estimated_price,
                "currency": "EUR",
                "airline": airline_name,
                "departure_time": departure_time,
                "arrival_time": arrival_time,
                "stops": 0,  # AviationStack free tier doesn't expose layover info
                "duration": duration_iso,
                "distance_km": price_stats.get("distance_km"),
                "number_of_bookable_seats": None,
                "cabin_class": "ECONOMY",
                "fare_basis": None,
                "scraped_at": datetime.now(),
                "provider_name": "aviationstack",
            }

        except Exception as e:
            logger.warning(f"[AviationStack] Failed to parse flight: {e}")
            return None
