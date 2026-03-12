"""
Signals Engine — Aggregates indicators and converts them to standard signal format.
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field

from app.core.analysis.technical import IndicatorResult


class StandardSignal(BaseModel):
    """Normalized format for any signal source (Technical, Sentiment, ML)."""
    symbol: str
    direction: str       # "BUY", "SELL", "NEUTRAL"
    strength: float      # 0.0 to 1.0
    source: str          # e.g., "TECH_CONFLUENCE", "SENTIMENT_NET"
    confidence: float    # 0.0 to 1.0
    reasoning: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


def normalize_technical_signals(symbol: str, confluence_data: Dict[str, Any]) -> StandardSignal:
    """Convert technical confluence into a StandardSignal."""
    return StandardSignal(
        symbol=symbol,
        direction=confluence_data.get("direction", "NEUTRAL"),
        strength=abs(confluence_data.get("agreement_ratio", 0.0)),
        source="TECH_CONFLUENCE",
        confidence=confluence_data.get("confidence", 0.0),
        reasoning=f"Tech Analysis: {confluence_data.get('buy_votes')} BUY vs {confluence_data.get('sell_votes')} SELL votes.",
        metadata=confluence_data
    )

def normalize_sentiment_signals(symbol: str, sentiment_data: Dict[str, Any]) -> StandardSignal:
    """Convert sentiment data into a StandardSignal."""
    return StandardSignal(
        symbol=symbol,
        direction=sentiment_data.get("signal", "NEUTRAL"),
        strength=sentiment_data.get("strength", 0.0),
        source="NEWS_SENTIMENT",
        confidence=sentiment_data.get("confidence", 0.0),
        reasoning=f"News: Base ({sentiment_data.get('base', {}).get('score', 0):.2f}) vs Quote ({sentiment_data.get('quote', {}).get('score', 0):.2f})",
        metadata={"base_reasoning": sentiment_data.get('base', {}).get('reasoning'),
                  "quote_reasoning": sentiment_data.get('quote', {}).get('reasoning')}
    )
