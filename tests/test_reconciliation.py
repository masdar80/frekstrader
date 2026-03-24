import pytest
from unittest.mock import AsyncMock, patch
from app.workers.market_watcher import MarketWatcher
from app.db.models import Trade

@pytest.mark.asyncio
async def test_reconciliation_trade_closed():
    watcher = MarketWatcher()
    
    # Mock open db trades
    mock_trade = Trade(id=1, symbol="EURUSD", status="open", external_id="pos123")
    
    # Mock broker positions (broker has NO positions = trade was closed)
    open_positions = []
    
    # Mock broker history
    mock_history = [
        {"id": "deal1", "position_id": "pos123", "symbol": "EURUSD", "profit": 5.0, "swap": -0.5, "commission": -0.2, "price": 1.1050}
    ]
    
    with patch("app.workers.market_watcher.async_session") as mock_session_maker, \
         patch("app.workers.market_watcher.crud.get_open_trades_by_external_id", new_callable=AsyncMock) as mock_get_trades, \
         patch("app.workers.market_watcher.broker.get_history", new_callable=AsyncMock) as mock_get_history, \
         patch("app.workers.market_watcher.crud.close_trade", new_callable=AsyncMock) as mock_close_trade, \
         patch("app.workers.market_watcher.crud.update_decision_outcome", new_callable=AsyncMock) as mock_update_outcome:
             
        # Setup mocks
        mock_db = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_db
        mock_get_trades.return_value = {"pos123": mock_trade}
        mock_get_history.return_value = mock_history
        
        # Run
        await watcher._reconcile_positions(open_positions)
        
        # Verify
        mock_get_history.assert_called_once_with(days=3)
        # expected profit: 5.0 - 0.5 - 0.2 = 4.3
        mock_close_trade.assert_called_once_with(mock_db, 1, 1.1050, 4.3)
        mock_update_outcome.assert_called_once_with(mock_db, 1, True)
        mock_db.commit.assert_called_once()

@pytest.mark.asyncio
async def test_reconciliation_trade_still_open():
    watcher = MarketWatcher()
    
    mock_trade = Trade(id=1, symbol="EURUSD", status="open", external_id="pos123")
    
    # Mock broker positions (broker HAS position = trade is still open)
    open_positions = [{"id": "pos123", "symbol": "EURUSD"}]
    
    with patch("app.workers.market_watcher.async_session") as mock_session_maker, \
         patch("app.workers.market_watcher.crud.get_open_trades_by_external_id", new_callable=AsyncMock) as mock_get_trades, \
         patch("app.workers.market_watcher.broker.get_history", new_callable=AsyncMock) as mock_get_history, \
         patch("app.workers.market_watcher.crud.close_trade", new_callable=AsyncMock) as mock_close_trade:
             
        mock_db = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_db
        mock_get_trades.return_value = {"pos123": mock_trade}
        
        await watcher._reconcile_positions(open_positions)
        
        # Verify no closure happened
        mock_get_history.assert_not_called()
        mock_close_trade.assert_not_called()
