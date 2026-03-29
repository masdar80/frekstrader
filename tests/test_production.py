import pytest
from app.core.analysis.position_sizer import PositionSizer
from app.core.analysis.trailing_stop import TrailingStopManager
from app.config import settings

def test_position_sizer_risk_cap():
    sizer = PositionSizer()
    balance = 1000.0
    risk_pct = 2.0 # 2% = $20
    
    # Case 1: Standard risk ($20 < $20 cap)
    settings.max_risk_amount_usd = 20.0
    vol, risk_usd = sizer.calculate_volume("EURUSD", balance, risk_pct, 0.0010)
    assert risk_usd <= 20.0
    
    # Case 2: Risk cap hit ($50 vs $20 cap)
    risk_pct_high = 5.0 # 5% = $50
    vol_capped, risk_usd_capped = sizer.calculate_volume("EURUSD", balance, risk_pct_high, 0.0010)
    assert risk_usd_capped <= 20.1 # Allow small float margin
    assert vol_capped < 0.05 # Should be lower than 5% volume

def test_trailing_stop_breakeven():
    manager = TrailingStopManager()
    
    # Buy trade at 1.1000, SL at 1.0950 (50 pips)
    # ATR = 10 pips (0.0010)
    # Breakeven multiplier = 2.0 (Move to BE after 20 pips profit)
    trade = {
        "id": "t1", "symbol": "EURUSD", "direction": "BUY",
        "open_price": 1.1000, "stop_loss": 1.0950, "take_profit": 1.1100
    }
    
    # Current price 1.1010 (10 pips profit) - No change
    new_sl = manager.check_and_calculate_new_sl(trade, 1.1010, 0.0010)
    assert new_sl is None
    
    # Current price 1.1025 (25 pips profit) - Move to Breakeven
    new_sl_be = manager.check_and_calculate_new_sl(trade, 1.1025, 0.0010)
    assert new_sl_be == 1.1000

def test_trailing_stop_atr_trailing():
    manager = TrailingStopManager()
    
    # Trade already at breakeven
    trade = {
        "id": "t1", "symbol": "EURUSD", "direction": "BUY",
        "open_price": 1.1000, "stop_loss": 1.1000, "take_profit": 1.1200
    }
    
    # ATR = 10 pips. Trailing multiplier = 3.0 (Trail by 30 pips)
    # Price moves to 1.1050. SL should move to 1.1050 - 0.0030 = 1.1020
    new_sl = manager.check_and_calculate_new_sl(trade, 1.1050, 0.0010)
    assert new_sl == 1.1020
    
    # Price moves back to 1.1040. SL should NOT move back
    new_sl_back = manager.check_and_calculate_new_sl(trade, 1.1040, 0.0010)
    assert new_sl_back is None
