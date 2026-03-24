import pytest
from datetime import datetime, timezone, timedelta
from app.core.analysis.calendar import EconomicCalendar
from app.config import settings

@pytest.mark.asyncio
async def test_calendar_safe_to_trade():
    calendar = EconomicCalendar()
    
    # Mock the cache with events
    now = datetime.now(timezone.utc)
    
    # Event 1: US NFP (High Impact) - happened 4 hours ago -> Safe
    # Event 2: ECB Rate (High Impact) - happens in 10 minutes -> Unsafe for EUR
    
    calendar._last_fetch = now.timestamp()
    calendar._events_cache = [
        {
            "title": "Non-Farm Employment Change",
            "country": "USD",
            "time_utc": now - timedelta(hours=4)
        },
        {
            "title": "Main Refinancing Rate",
            "country": "EUR",
            "time_utc": now + timedelta(minutes=10)
        }
    ]
    
    # Check USDJPY -> Only USD is affected. Last USD event was 4 hrs ago, next is nothing.
    # Should be SAFE
    usd_res = await calendar.is_safe_to_trade("USDJPY")
    assert usd_res["safe"] == True
    
    # Check EURUSD -> EUR is affected by event in 10 mins. 10 mins < 30 mins blackout window.
    # Should be UNSAFE
    eur_res = await calendar.is_safe_to_trade("EURUSD")
    assert eur_res["safe"] == False
    assert "EUR" in eur_res["reason"]
    assert "Main Refinancing Rate" in eur_res["upcoming_event"]
