import pandas as pd
from typing import Dict, Any

class MarketRegimeDetector:
    """
    Detects the current market regime based on technical indicators.
    Regimes:
      - TRENDING_UP
      - TRENDING_DOWN
      - RANGING
      - VOLATILE
    """
    
    def __init__(self):
        pass

    def detect(self, symbol: str, ta_results: Dict[str, list]) -> Dict[str, Any]:
        """
        Determines the regime based on the 4h timeframe (or 1h if 4h is unavailable).
        Expects ta_results to be grouped by indicator name, containing IndicatorResult objects.
        """
        adx_val = 20.0
        plus_di = 20.0
        minus_di = 20.0
        ema20 = 0.0
        ema50 = 0.0
        price = 0.0
        atr = 0.0
        
        # Use 4h as primary, fallback to 1h
        tf_used = "1h"
        
        if "ADX" in ta_results:
            for r in ta_results["ADX"]:
                if r.timeframe == "4h":
                    adx_val = r.details.get("adx", 20)
                    plus_di = r.details.get("plus_di", 20)
                    minus_di = r.details.get("minus_di", 20)
                    tf_used = "4h"
                    break
            else:
                for r in ta_results["ADX"]:
                    if r.timeframe == "1h":
                        adx_val = r.details.get("adx", 20)
                        plus_di = r.details.get("plus_di", 20)
                        minus_di = r.details.get("minus_di", 20)
                        break

        if "EMA_CROSS" in ta_results:
            for r in ta_results["EMA_CROSS"]:
                if r.timeframe == tf_used:
                    ema20 = r.details.get("ema20", 0)
                    ema50 = r.details.get("ema50", 0)
                    price = r.details.get("price", 0)
                    break
                    
        if "ATR" in ta_results:
            for r in ta_results["ATR"]:
                if r.timeframe == tf_used:
                    atr = r.details.get("atr", 0)
                    break
                    
        # Regime logic
        regime = "RANGING"
        confidence = 0.5
        
        is_trending = adx_val > 25
        
        if is_trending:
            if plus_di > minus_di and price > ema50:
                regime = "TRENDING_UP"
                confidence = min(1.0, adx_val / 50.0)
            elif minus_di > plus_di and price < ema50:
                regime = "TRENDING_DOWN"
                confidence = min(1.0, adx_val / 50.0)
            else:
                # ADX says trend, but price action contradicts
                regime = "VOLATILE"
                confidence = 0.6
        else:
            if adx_val < 20:
                regime = "RANGING"
                confidence = max(0.5, 1.0 - (adx_val / 20.0))
            else:
                regime = "CHOPPY"
                confidence = 0.5
                
        # If ATR is very high relative to price (e.g. news event)
        if price > 0 and (atr / price) > 0.005:  # roughly 50 pips on EURUSD
            regime = "VOLATILE"
            confidence = 0.8
            
        return {
            "regime": regime,
            "confidence": round(confidence, 3),
            "adx": round(adx_val, 2),
            "timeframe": tf_used,
            "ta_raw_results": ta_results
        }

regime_detector = MarketRegimeDetector()
