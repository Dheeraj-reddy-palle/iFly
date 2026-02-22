"""
Synthetic Flight Offers Provider — controlled fallback.

Generates realistic price estimates using historical statistics
from the database when real API providers are exhausted.

Rules:
  - EUR only
  - Max 20% of daily rows
  - Clearly tagged provider_name = 'synthetic'
  - Prices bounded within realistic ranges per route
"""
import logging
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("Provider.Synthetic")

# Realistic airline codes for synthetic generation
SYNTHETIC_AIRLINES = [
    "Air India", "IndiGo", "SpiceJet", "Vistara",
    "Emirates", "Lufthansa", "British Airways",
    "Singapore Airlines", "Qatar Airways", "Delta Air Lines",
]

# Default price ranges by route type (EUR) when no DB stats exist
DEFAULT_PRICE_RANGES = {
    "domestic": (40, 250),
    "short_haul": (100, 500),
    "long_haul": (250, 1200),
}

# Haversine distances for classification
DOMESTIC_THRESHOLD_KM = 2000
SHORT_HAUL_THRESHOLD_KM = 5000


class SyntheticProvider:
    """
    Generates synthetic flight offers based on historical route statistics.

    This is NOT a FlightProviderInterface implementation because it requires
    a database session. It's used directly by the ProviderManager as a
    last-resort fallback.
    """

    def __init__(self, db: Session):
        self._db = db
        self._route_stats_cache: Dict[str, Dict] = {}
        self._daily_synthetic_count = 0
        self._max_daily_synthetic = 200  # Cap at 200 synthetic rows per day

    @property
    def provider_name(self) -> str:
        return "synthetic"

    async def fetch_offers(
        self, origin: str, destination: str, departure_date: str
    ) -> List[Dict[str, Any]]:
        """Generate synthetic offers based on historical route statistics."""
        if self._daily_synthetic_count >= self._max_daily_synthetic:
            logger.warning("[Synthetic] Daily cap reached. Skipping.")
            return []

        route_key = f"{origin}-{destination}"
        stats = self._get_route_stats(origin, destination)

        # Generate 2-5 synthetic offers per route/date
        num_offers = random.randint(2, 5)
        offers = []

        for _ in range(num_offers):
            offer = self._generate_offer(origin, destination, departure_date, stats)
            if offer:
                offers.append(offer)
                self._daily_synthetic_count += 1

        logger.info(f"[Synthetic] Generated {len(offers)} offers for {route_key} on {departure_date}")
        return offers

    async def is_available(self) -> bool:
        """Always available as long as daily cap isn't hit."""
        return self._daily_synthetic_count < self._max_daily_synthetic

    async def remaining_quota(self) -> int:
        """Remaining synthetic offers for today."""
        return max(0, self._max_daily_synthetic - self._daily_synthetic_count)

    def _get_route_stats(self, origin: str, destination: str) -> Dict:
        """Fetch historical price statistics for a route from DB."""
        route_key = f"{origin}-{destination}"

        if route_key in self._route_stats_cache:
            return self._route_stats_cache[route_key]

        try:
            query = text("""
                SELECT 
                    AVG(price) as mean_price,
                    STDDEV(price) as std_price,
                    MIN(price) as min_price,
                    MAX(price) as max_price,
                    AVG(distance_km) as avg_distance,
                    COUNT(*) as sample_count
                FROM flight_offers
                WHERE origin = :origin AND destination = :dest
                  AND price > 0
            """)
            row = self._db.execute(query, {"origin": origin, "dest": destination}).fetchone()

            if row and row.sample_count and row.sample_count > 5:
                stats = {
                    "mean": float(row.mean_price),
                    "std": float(row.std_price) if row.std_price else float(row.mean_price) * 0.2,
                    "min": float(row.min_price),
                    "max": float(row.max_price),
                    "distance_km": float(row.avg_distance) if row.avg_distance else None,
                    "sample_count": int(row.sample_count),
                }
            else:
                stats = self._default_stats(origin, destination)

            self._route_stats_cache[route_key] = stats
            return stats

        except Exception as e:
            logger.error(f"[Synthetic] DB query failed for {route_key}: {e}")
            return self._default_stats(origin, destination)

    def _default_stats(self, origin: str, destination: str) -> Dict:
        """Fallback stats when no historical data exists."""
        # Rough classification based on common knowledge
        domestic_codes = {"DEL", "BOM", "BLR", "HYD", "CCU", "MAA", "GOI"}
        is_domestic = origin in domestic_codes and destination in domestic_codes

        if is_domestic:
            price_range = DEFAULT_PRICE_RANGES["domestic"]
        else:
            price_range = DEFAULT_PRICE_RANGES["long_haul"]

        mean = (price_range[0] + price_range[1]) / 2
        return {
            "mean": mean,
            "std": mean * 0.25,
            "min": price_range[0],
            "max": price_range[1],
            "distance_km": None,
            "sample_count": 0,
        }

    def _generate_offer(
        self, origin: str, destination: str, departure_date: str, stats: Dict
    ) -> Optional[Dict[str, Any]]:
        """Generate a single synthetic offer."""
        try:
            # Price: Gaussian around historical mean, clamped to realistic range
            price = random.gauss(stats["mean"], stats["std"])
            price = max(stats["min"] * 0.8, min(stats["max"] * 1.2, price))
            price = round(max(10.0, price), 2)  # Floor at €10

            # Airline: random from realistic set
            airline = random.choice(SYNTHETIC_AIRLINES)

            # Times: random departure hour
            dep_date = datetime.strptime(departure_date, "%Y-%m-%d")
            dep_hour = random.randint(5, 23)
            dep_minute = random.choice([0, 15, 30, 45])
            departure_time = dep_date.replace(hour=dep_hour, minute=dep_minute)

            # Duration: estimate from distance or default
            if stats.get("distance_km") and stats["distance_km"] > 0:
                flight_hours = stats["distance_km"] / 800  # ~800 km/h average
            else:
                flight_hours = random.uniform(1.5, 12.0)

            duration_minutes = int(flight_hours * 60)
            duration_iso = f"PT{duration_minutes // 60}H{duration_minutes % 60}M"
            arrival_time = departure_time + timedelta(minutes=duration_minutes)

            # Stops
            stops = 0 if random.random() < 0.6 else (1 if random.random() < 0.8 else 2)

            return {
                "origin": origin,
                "destination": destination,
                "departure_date": departure_time,
                "return_date": None,
                "price": price,
                "currency": "EUR",
                "airline": airline,
                "departure_time": departure_time,
                "arrival_time": arrival_time,
                "stops": stops,
                "duration": duration_iso,
                "distance_km": stats.get("distance_km"),
                "number_of_bookable_seats": random.randint(1, 9),
                "cabin_class": "ECONOMY",
                "fare_basis": "SYNTHETIC",
                "scraped_at": datetime.now(),
                "provider_name": "synthetic",
            }

        except Exception as e:
            logger.error(f"[Synthetic] Failed to generate offer: {e}")
            return None
