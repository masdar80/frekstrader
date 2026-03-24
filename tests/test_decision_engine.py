import pytest
from app.core.brain.decision_engine import DecisionEngine
from app.core.analysis.signals import StandardSignal
from app.config import settings, TradingMode

def test_decision_engine_unanimous_buy(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "use_ai_sentiment", False)
    
    engine = DecisionEngine()
    
    # Technical signal - very high confidence
    tech_sig = StandardSignal(
        source="TECH_CONFLUENCE",
        symbol="EURUSD",
        direction="BUY",
        strength=1.0,
        confidence=1.0,
        reasoning="Max confidence buy",
        metadata={"buy_votes": 10, "sell_votes": 0}
    )
    
    decision = engine.evaluate_signals("EURUSD", [tech_sig])
    
    assert decision.action == "BUY"


    assert decision.confidence > 0.6

def test_decision_engine_mixed_signals():
    settings.trading_mode = TradingMode.BALANCED
    engine = DecisionEngine()
    
    # Technical signal but with few indicators
    tech_sig = StandardSignal(
        source="TECH_CONFLUENCE",
        symbol="EURUSD",
        direction="BUY",
        strength=0.8,
        confidence=0.85,
        reasoning="Weak buy",
        metadata={"buy_votes": 2, "sell_votes": 1}
    )
    
    decision = engine.evaluate_signals("EURUSD", [tech_sig])
    
    # Should reject due to settings.min_indicators_required (default is often 3)
    assert decision.action == "REJECT"

def test_decision_engine_contradiction():
    settings.trading_mode = TradingMode.BALANCED
    engine = DecisionEngine()
    
    # Technical BUY, but Sentiment SELL
    tech_sig = StandardSignal(
        source="TECH_CONFLUENCE", symbol="EURUSD", direction="BUY",
        strength=0.8, confidence=0.85, reasoning="Tech buy",
        metadata={"buy_votes": 5}
    )
    sent_sig = StandardSignal(
        source="NEWS_SENTIMENT", symbol="EURUSD", direction="SELL",
        strength=0.7, confidence=0.7, reasoning="Negative news"
    )
    
    decision = engine.evaluate_signals("EURUSD", [tech_sig, sent_sig])
    
    # Confidence should be reduced for contradiction
    assert decision.confidence < 0.8

