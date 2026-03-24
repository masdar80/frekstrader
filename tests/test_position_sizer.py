import pytest
from app.core.risk.position_sizer import position_sizer

def test_jpy_tick_value():
    symbol_info = {
        "contract_size": 100000,
        "point": 0.001,
        "min_volume": 0.01,
        "max_volume": 100.0,
        "volume_step": 0.01
    }
    
    # Buy USDJPY at 150.000, account equity is $10,000, risk is 1% ($100), ATR is 0.500
    res = position_sizer.calculate(
        symbol="USDJPY",
        direction="BUY",
        current_price=150.000,
        account_equity=10000.0,
        atr_value=0.500,
        symbol_info=symbol_info,
        confidence=0.8
    )
    
    assert res["allowed"] is True
    
    # Calculate expectation based on current settings
    from app.config import settings
    base_risk_pct = settings.effective_max_risk_pct
    min_conf = settings.confidence_threshold
    conf_multiplier = 0.5 + ((0.8 - min_conf) / (1.0 - min_conf) * 0.5) if 0.8 > min_conf else 0.5
    expected_risk = 10000.0 * (base_risk_pct * conf_multiplier / 100.0)
    
    assert res["risk_amount"] == pytest.approx(expected_risk, 0.1)
    assert res["volume"] > 0
    assert "stop_loss" in res
    
    # Ensure SL price is correctly rounded to 3 decimal places
    sl_str = str(res["stop_loss"])
    assert len(sl_str.split(".")[1]) <= 3

def test_eurusd_tick_value():
    symbol_info = {
        "contract_size": 100000,
        "point": 0.00001,
        "min_volume": 0.01,
        "max_volume": 100.0,
        "volume_step": 0.01
    }
    
    res = position_sizer.calculate(
        symbol="EURUSD",
        direction="SELL",
        current_price=1.10000,
        account_equity=10000.0,
        atr_value=0.00200,
        symbol_info=symbol_info,
        confidence=0.9
    )
    
    assert res["allowed"] is True
    assert res["volume"] > 0
    
    # Round to 5
    sl_str = str(res["stop_loss"])
    assert len(sl_str.split(".")[1]) <= 5
