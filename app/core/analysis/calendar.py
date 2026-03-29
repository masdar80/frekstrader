import time
import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from app.config import settings
from app.utils.logger import logger

class EconomicCalendar:
    def __init__(self):
        self._events_cache: List[Dict[str, Any]] = []
        self._last_fetch = 0.0
        self._fetch_interval = 21600 # 6 hours

    async def fetch_events(self):
        """Fetch the weekly calendar from ForexFactory JSON feed."""
        now = time.time()
        if now - self._last_fetch < self._fetch_interval and self._events_cache:
            return
            
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    
                    # Filter only HIGH impact events
                    high_impact = [e for e in data if e.get("impact") == "High"]
                    
                    parsed_events = []
                    for e in high_impact:
                        try:
                            # Parse "2024-03-24T18:00:00-04:00" format timestamp
                            # Date formatted as ISO8601 string
                            dt = datetime.fromisoformat(e["date"])
                            # Ensure it is UTC aware
                            dt_utc = dt.astimezone(timezone.utc)
                            
                            parsed_events.append({
                                "title": e.get("title"),
                                "country": e.get("country"),
                                "time_utc": dt_utc
                            })
                        except Exception as parse_err:
                            logger.error(f"Error parsing date {e.get('date')}: {parse_err}")
                            continue
                            
                    self._events_cache = parsed_events
                    self._last_fetch = now
                    logger.info(f"📅 Updated Economic Calendar: {len(self._events_cache)} high-impact events this week")
                else:
                    logger.error(f"Calendar fetch failed: returned {res.status_code}")
        except Exception as e:
            logger.error(f"Calendar Network Error: {e}")

    async def is_safe_to_trade(self, symbol: str) -> Dict[str, Any]:
        """Check if it's safe to trade given the blackout window around high impact news."""
        await self.fetch_events()
        
        if not self._events_cache:
            # Phase 1.4: Fail-closed policy
            if self._last_fetch > 0:
                # We have fetched before, but current cache is empty (failed refresh)
                # Block for safety during potential high-impact news spikes
                return {
                    "safe": False, 
                    "reason": "Calendar data stale — blocking for safety", 
                    "upcoming_event": "STALE_DATA_PROTECTION"
                }
            else:
                # First startup or never successfully fetched — allow trading but log warning
                return {"safe": True, "reason": "No calendar data (initial startup)", "upcoming_event": None}
            
        now_utc = datetime.now(timezone.utc)
        blackout_delta = timedelta(minutes=settings.news_blackout_minutes)
        
        # Currencies affected by this pair (e.g. 'EURUSD' -> ['EUR', 'USD'])
        base = symbol[:3]
        quote = symbol[3:]
        affected_currencies = [base, quote]
        
        for event in self._events_cache:
            if event["country"] in affected_currencies:
                event_time = event["time_utc"]
                
                # Check if current time is within [event_time - blackout, event_time + blackout]
                if event_time - blackout_delta <= now_utc <= event_time + blackout_delta:
                    mins_to_event = (event_time - now_utc).total_seconds() / 60
                    status = "Upcoming" if mins_to_event > 0 else "Recent"
                    
                    reason_str = f"{status} HIGH impact {event['country']} news: '{event['title']}' ({abs(int(mins_to_event))} mins away)"
                    return {"safe": False, "reason": reason_str, "upcoming_event": event["title"]}
                    
        return {"safe": True, "reason": "Clear", "upcoming_event": None}

# Global Instance
economic_calendar = EconomicCalendar()
