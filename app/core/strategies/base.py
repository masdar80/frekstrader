import abc
from typing import Dict, Any, List
from app.core.analysis.signals import StandardSignal

class BaseStrategy(abc.ABC):
    """
    Abstract base class for trading strategies.
    Allows for multiple strategies to run concurrently and vote
    on the final direction.
    """
    def __init__(self, name: str):
        self.name = name
        
    @abc.abstractmethod
    def evaluate(self, symbol: str, ta_results: Dict[str, Any], regime_info: Dict[str, Any]) -> StandardSignal:
        pass

class TrendFollowingStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("TREND_FOLLOWING")
        
    def evaluate(self, symbol: str, ta_results: Dict[str, Any], regime_info: Dict[str, Any]) -> StandardSignal:
        regime = regime_info.get("regime", "UNKNOWN")
        if regime not in ["TRENDING_UP", "TRENDING_DOWN"]:
            return StandardSignal(symbol=symbol, direction="NEUTRAL", strength=0.0, source=self.name, confidence=0.0, reasoning="Not trending")
            
        direction = "BUY" if regime == "TRENDING_UP" else "SELL"
        confidence = regime_info.get("confidence", 0.5)
        
        return StandardSignal(symbol=symbol, direction=direction, strength=confidence, source=self.name, confidence=confidence, reasoning=f"Trend is {direction}")

class MeanReversionStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("MEAN_REVERSION")
        
    def evaluate(self, symbol: str, ta_results: Dict[str, Any], regime_info: Dict[str, Any]) -> StandardSignal:
        regime = regime_info.get("regime", "UNKNOWN")
        if regime != "RANGING":
            return StandardSignal(symbol=symbol, direction="NEUTRAL", strength=0.0, source=self.name, confidence=0.0, reasoning="Not ranging")
            
        # Check RSI for overbought/oversold
        rsi_1h = 50
        if "RSI" in ta_results:
            for r in ta_results["RSI"]:
                if r.timeframe == "1h":
                    rsi_1h = r.details.get("rsi", 50) # Fallback to 50 if missing
                    # Actually indicatorResult value is in r.value
                    rsi_1h = r.value
                    break
                    
        direction = "NEUTRAL"
        confidence = 0.0
        
        if rsi_1h > 75:
            direction = "SELL"
            confidence = min(1.0, (rsi_1h - 75) / 25)
        elif rsi_1h < 25:
            direction = "BUY"
            confidence = min(1.0, (25 - rsi_1h) / 25)
            
        return StandardSignal(symbol=symbol, direction=direction, strength=confidence, source=self.name, confidence=confidence, reasoning=f"RSI is {rsi_1h}")

class BreakoutStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("BREAKOUT")
        
    def evaluate(self, symbol: str, ta_results: Dict[str, Any], regime_info: Dict[str, Any]) -> StandardSignal:
        # Placeholder for breakout logic using Bollinger Bands
        return StandardSignal(symbol=symbol, direction="NEUTRAL", strength=0.0, source=self.name, confidence=0.0, reasoning="WIP")
