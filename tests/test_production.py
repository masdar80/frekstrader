import pytest
from app.core.risk.position_sizer import position_sizer
from app.config import settings

def test_position_sizer_risk_cap():
    symbol_info = {
        "contract_size": 100000,
        "point": 0.00001,
        "min_volume": 0.01,
        "max_volume": 100.0,
        "volume_step": 0.01
    }
    balance = 1000.0
    # 2% risk on $1000 = $20
    # Our cap is $20
    original_cap = settings.max_risk_amount_usd
    settings.max_risk_amount_usd = 20.0
    
    try:
        res = position_sizer.calculate(
            symbol="EURUSD",
            direction="BUY",
            current_price=1.1000,
            account_equity=balance,
            atr_value=0.00010,
            symbol_info=symbol_info,
            confidence=1.0 # Max confidence to get 100% of risk_pct
        )
        
        assert res["allowed"] is True
        assert res["risk_amount"] <= 20.01
        assert res["volume"] == 1.0
    finally:
        settings.max_risk_amount_usd = original_cap

def test_position_sizer_extreme_risk_cap():
    symbol_info = {
        "contract_size": 100000,
        "point": 0.00001,
        "min_volume": 0.01,
        "max_volume": 100.0,
        "volume_step": 0.01
    }
    balance = 1000.0
    # Set cap to $10
    original_cap = settings.max_risk_amount_usd
    settings.max_risk_amount_usd = 10.0
    
    try:
        res = position_sizer.calculate(
            symbol="EURUSD",
            direction="BUY",
            current_price=1.1000,
            account_equity=balance,
            atr_value=0.00010,
            symbol_info=symbol_info,
            confidence=1.0
        )
        
        assert res["allowed"] is True
        assert res["risk_amount"] <= 10.01
        assert res["volume"] == 0.5 # $10 / $20_per_lot = 0.5 lots
    finally:
        settings.max_risk_amount_usd = original_cap
