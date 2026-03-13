import pytest
from app.core.brain.decision_engine import SkepticalBrain
from app.core.analysis.technical import StandardSignal

def test_decision_engine_unanimous_buy():
    brain = SkepticalBrain()
    
    # 4 Buy signals
    signals = [
        StandardSignal("RSI", "BUY", 0.8),
        StandardSignal("MACD", "BUY", 0.9),
        StandardSignal("Bollinger", "BUY", 0.7),
        StandardSignal("Sentiment", "BUY", 0.75, is_sentiment=True)
    ]
    
    decision = brain.evaluate("EURUSD", signals)
    
    assert decision.action == "BUY"
    assert decision.confidence > 0.7

def test_decision_engine_mixed_signals():
    brain = SkepticalBrain()
    
    # Mixed signals (3 Buy, 2 Sell) point to HOLD or REJECT because of skepticism
    signals = [
        StandardSignal("RSI", "BUY", 0.8),
        StandardSignal("Bollinger", "BUY", 0.7),
        StandardSignal("ADX", "SELL", 0.9),
        StandardSignal("MACD", "SELL", 0.8),
        StandardSignal("Sentiment", "BUY", 0.6, is_sentiment=True)
    ]
    
    decision = brain.evaluate("EURUSD", signals)
    
    # Due to skepticism penalty for mixed directions, it should reject or hold
    assert decision.action in ["HOLD", "REJECT"]

def test_decision_engine_not_enough_indicators():
    brain = SkepticalBrain()
    
    # 1 signal
    signals = [
        StandardSignal("RSI", "BUY", 0.8)
    ]
    
    decision = brain.evaluate("EURUSD", signals)
    assert decision.action == "REJECT"
    assert "Not enough indicators" in decision.reasoning
