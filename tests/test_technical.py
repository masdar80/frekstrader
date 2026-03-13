import pytest
import pandas as pd
from app.core.analysis.technical import TechnicalAnalyzer

@pytest.fixture
def sample_df():
    # Create enough mock daily candles for pandas-ta (needs ~20 for BB, 14 for ADX, 26 for MACD)
    # We need at least 30 candles to compute MACD safely.
    import numpy as np
    dates = pd.date_range("2024-01-01", periods=40, freq="D")
    
    # Generate some realistic-looking random walking prices
    closes = np.cumprod(1 + np.random.normal(0, 0.01, size=40)) * 1.1000
    
    df = pd.DataFrame({
        "time": dates,
        "open": closes * np.random.normal(1, 0.001, size=40),
        "high": closes * 1.005,
        "low": closes * 0.995,
        "close": closes,
        "tick_volume": np.random.randint(100, 1000, size=40)
    })
    return df

def test_bollinger_bands_ordering(sample_df):
    analyzer = TechnicalAnalyzer()
    res = analyzer._calc_bollinger(sample_df, "15m")
    
    assert res is not None
    assert "lower" in res.details
    
    lower = res.details["lower"]
    middle = res.details["middle"]
    upper = res.details["upper"]
    
    assert lower < upper
    assert lower <= middle <= upper

def test_adx_ordering(sample_df):
    analyzer = TechnicalAnalyzer()
    res = analyzer._calc_adx(sample_df, "15m")
    
    assert res is not None
    assert "adx" in res.details
    
    assert res.details["adx"] >= 0
    assert res.details["plus_di"] >= 0
    assert res.details["minus_di"] >= 0
