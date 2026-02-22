"""
Abstract base class for all flight data providers.
Every provider must return offers in an identical schema
so the downstream ML pipeline remains provider-agnostic.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class FlightProviderInterface(ABC):
    """
    Contract that every flight data provider must satisfy.
    
    All providers MUST:
      - Return offers in EUR currency
      - Include provider_name in each offer dict
      - Follow the identical dictionary schema
      - Handle their own authentication and rate limiting
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier for this provider (e.g. 'amadeus', 'kiwi', 'synthetic')."""
        ...

    @abstractmethod
    async def fetch_offers(
        self, origin: str, destination: str, departure_date: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch flight offers for a given route and date.
        
        Args:
            origin: IATA airport code (e.g. 'DEL')
            destination: IATA airport code (e.g. 'BOM')
            departure_date: ISO date string (e.g. '2026-03-15')
            
        Returns:
            List of offer dicts matching the FlightOffer schema.
            Empty list on failure (never raise).
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """
        Check if this provider is configured and has remaining quota.
        Returns False if credentials are missing or quota is exhausted.
        """
        ...

    @abstractmethod
    async def remaining_quota(self) -> int:
        """
        Estimated remaining API calls for today.
        Returns -1 if unlimited (e.g. synthetic provider).
        """
        ...
