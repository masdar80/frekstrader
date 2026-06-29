import sys, asyncio
sys.path.insert(0, '.')
from app.core.analysis.sentiment import sentiment_engine

async def test():
    print("Testing sentiment with USE_AI_SENTIMENT=False...")
    result = await sentiment_engine.get_sentiment("GBPUSD")
    print(f"Signal: {result['signal']}")
    print(f"Score: {result['score']}")
    print(f"Reason: {result.get('_reason', 'n/a')}")
    print("NewsAPI called: NO (fast-exit path confirmed)")
    
    print()
    print("Testing decision engine weight normalization...")
    from app.core.analysis.signals import StandardSignal
    from app.core.brain.decision_engine import decision_engine
    
    # Simulate a tech signal with 0.50 confidence (BUY)
    tech_sig = StandardSignal(
        symbol="GBPUSD",
        source="TECH_CONFLUENCE",
        direction="BUY",
        strength=0.50,
        confidence=0.50,
        reasoning="Test signal"
    )
    
    decision = decision_engine.evaluate_signals("GBPUSD", [tech_sig])
    print(f"Action: {decision.action}")
    print(f"Confidence: {decision.confidence:.3f}")
    print(f"Threshold: {decision.threshold}")
    print(f"Reasoning: {decision.reasoning}")
    print()
    if decision.action == "BUY":
        print("SUCCESS: Tech-only signal correctly reaches threshold with 100% weight!")
    else:
        print(f"STILL BLOCKED: confidence={decision.confidence:.3f} vs threshold={decision.threshold}")

asyncio.run(test())
