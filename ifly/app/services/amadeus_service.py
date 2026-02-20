import httpx
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

class AmadeusService:
    def __init__(self):
        self.base_url = settings.amadeus_base_url
        self.api_key = settings.amadeus_api_key
        self.api_secret = settings.amadeus_api_secret
        
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    async def _get_token(self) -> str:
        """
        Retrieves the OAuth 2.0 access token from Amadeus. 
        Caches it locally and returns it. Automatically refreshes 60 seconds prior to expiry.
        """
        # If token exists and is valid (with a 60-second buffer), return it immediately
        if self._access_token and self._token_expiry:
            if datetime.now() < (self._token_expiry - timedelta(seconds=60)):
                return self._access_token
                
        # Token needs refreshing
        auth_url = f"{self.base_url}/v1/security/oauth2/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.api_secret
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(auth_url, data=data)
                response.raise_for_status()
                
                auth_data = response.json()
                self._access_token = auth_data.get("access_token")
                expires_in = auth_data.get("expires_in", 1799)
                
                # Set new expiry using absolute time
                self._token_expiry = datetime.now() + timedelta(seconds=expires_in)
                return self._access_token
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Amadeus Authentication failed with status code: {e.response.status_code}")
            raise HTTPException(status_code=500, detail="Upstream authentication provider failed.")
        except Exception as e:
            logger.error(f"Failed to fetch Amadeus Token: {str(e)}")
            raise HTTPException(status_code=500, detail="Could not connect to travel partner.")

    async def search_flights(self, 
                             origin: str, 
                             destination: str, 
                             departure_date: str, 
                             return_date: Optional[str] = None, 
                             adults: int = 1) -> List[Dict[str, Any]]:
        """
        Queries the Amadeus Flight Offers Search API, normalizing the complex JSON structure 
        into our flat internal dictionary model for DB usage.
        """
        token = await self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.amadeus+json"
        }
        
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "adults": adults,
            "max": 50  # Let's cap at 50 to avoid massive payloads right now
        }
        
        if return_date:
            params["returnDate"] = return_date
            
        search_url = f"{self.base_url}/v2/shopping/flight-offers"
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(search_url, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                # If everything succeeds, normalize the output into our DB representation format
                return self._normalize_offers(data)
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("Amadeus Rate Limit Exceeded")
                raise HTTPException(status_code=429, detail="Rate limit exceeded downstream.")
            if e.response.status_code == 401:
                # Force token refresh next time around
                self._access_token = None 
                self._token_expiry = None
                raise HTTPException(status_code=502, detail="Upstream service authentication invalidated.")
                
            logger.error(f"Amadeus Search API failed: status {e.response.status_code}")
            raise HTTPException(status_code=e.response.status_code, detail="Downstream travel API lookup failed")
        except httpx.RequestError as e:
            logger.error(f"Network error querying Amadeus: {e}")
            raise HTTPException(status_code=503, detail="Downstream partner is unreachable.")
            
    def _normalize_offers(self, amadeus_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extracts complex hierarchical data into flat format mappings.
        Will map internal keys `departure_time`, `arrival_time`, `duration` natively.
        Uses exact ISO-8601 string for `duration` (e.g. PT2H15M) from the API.
        """
        offers = []
        dictionaries = amadeus_response.get("dictionaries", {})
        airline_dict = dictionaries.get("carriers", {})
        
        for item in amadeus_response.get("data", []):
            try:
                # Basic pricing 
                price_data = item.get("price", {})
                price = float(price_data.get("total", 0.0))
                currency = price_data.get("currency", "UNKNOWN")
                
                # Fetch only the outbound itinerary at [0] for duration analysis
                itineraries = item.get("itineraries", [])
                if not itineraries:
                    continue
                    
                outbound = itineraries[0]
                total_duration = outbound.get("duration", "") # Amadeus outputs ISO format already: PT2H15M
                segments = outbound.get("segments", [])
                
                if not segments:
                    continue
                    
                # Stops = total layovers between flight bounds
                stops = max(0, len(segments) - 1)
                
                # Departure Info
                first_segment = segments[0]
                departure_time_str = first_segment.get("departure", {}).get("at")
                departure_time = datetime.fromisoformat(departure_time_str) if departure_time_str else None
                origin_code = first_segment.get("departure", {}).get("iataCode")
                
                # Airline name
                airline_code = first_segment.get("carrierCode")
                airline = airline_dict.get(airline_code, airline_code)
                
                # Arrival Info
                last_segment = segments[-1]
                arrival_time_str = last_segment.get("arrival", {}).get("at")
                arrival_time = datetime.fromisoformat(arrival_time_str) if arrival_time_str else None
                dest_code = last_segment.get("arrival", {}).get("iataCode")
                
                # We expect the `return_date` in purely string YYYY-MM-DD format based on user input, 
                # resolving it back to a datetime requires mapping against outbound flight [1] if it exists
                return_date = None
                if len(itineraries) > 1:
                    inbound_first_seg = itineraries[1].get("segments", [])[0]
                    ret_dep_time_str = inbound_first_seg.get("departure", {}).get("at")
                    return_date = datetime.fromisoformat(ret_dep_time_str) if ret_dep_time_str else None
                
                # Format into internal structure mapping exactly to what SQLAlchemy expects
                offer = {
                    "origin": origin_code,
                    "destination": dest_code,
                    "departure_date": departure_time, # Using the exact datetime as requested for departure representation
                    "return_date": return_date,
                    "price": price,
                    "currency": currency,
                    "airline": airline,
                    "departure_time": departure_time,
                    "arrival_time": arrival_time,
                    "stops": stops,
                    "duration": total_duration,
                    "scraped_at": datetime.now()
                }
                
                offers.append(offer)
            except Exception as e:
                # If one single flight offer structurally breaks during decoding, we should swallow the single failure
                # and continue yielding the rest rather than throwing 500 for the entire pipeline
                logger.warning(f"Failed parsing single flight offer. Skipping. Cause: {e}")
                
        return offers
