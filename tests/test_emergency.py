import pytest
from unittest.mock import AsyncMock, patch
from app.workers.market_watcher import MarketWatcher

@pytest.mark.asyncio
async def test_emergency_pause_resume():
    watcher = MarketWatcher()
    
    # Verify initial state
    assert not watcher.is_paused
    
    # Pause
    watcher.pause()
    assert watcher.is_paused
    
    # Run cycle should return immediately if paused
    with patch("app.workers.market_watcher.broker.get_account_info", new_callable=AsyncMock) as mock_get_account:
        await watcher._run_cycle()
        mock_get_account.assert_not_called()
        
    # Resume
    watcher.resume()
    assert not watcher.is_paused

@pytest.mark.asyncio
async def test_emergency_close_all():
    watcher = MarketWatcher()
    
    mock_positions = [
        {"id": "pos1", "symbol": "EURUSD"},
        {"id": "pos2", "symbol": "USDJPY"}
    ]
    
    with patch("app.workers.market_watcher.broker.get_positions", new_callable=AsyncMock) as mock_get_pos, \
         patch("app.workers.market_watcher.broker.close_position", new_callable=AsyncMock) as mock_close_pos:
             
        mock_get_pos.return_value = mock_positions
        mock_close_pos.return_value = {"success": True}
        
        await watcher.emergency_close_all()
        
        assert watcher.is_paused
        mock_close_pos.assert_any_call("pos1")
        mock_close_pos.assert_any_call("pos2")
        assert mock_close_pos.call_count == 2
