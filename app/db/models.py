"""
Database models for ForeksTrader.
Stores trades, decisions, signals, and account snapshots.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, JSON, Enum as SAEnum
from app.db.database import Base
from app.utils.helpers import utcnow


class Trade(Base):
    """Executed trade record."""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(100), nullable=True, index=True)  # MetaAPI position ID
    symbol = Column(String(20), nullable=False, index=True)
    direction = Column(String(10), nullable=False)  # BUY or SELL
    volume = Column(Float, nullable=False)
    open_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    profit = Column(Float, nullable=True)
    profit_pips = Column(Float, nullable=True)
    status = Column(String(20), default="open")  # open, closed, cancelled
    opened_at = Column(DateTime, default=utcnow)
    closed_at = Column(DateTime, nullable=True)
    close_reason = Column(String(50), nullable=True)  # tp, sl, emergency, manual, news
    strategy_version = Column(String(50), nullable=True)
    trading_mode = Column(String(30), nullable=True)
    metadata_json = Column(JSON, nullable=True)


class Decision(Base):
    """Every decision the brain makes, stored for audit."""
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=utcnow, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    action = Column(String(20), nullable=False)  # BUY, SELL, REJECT, HOLD
    confidence = Column(Float, nullable=True)
    trading_mode = Column(String(30), nullable=True)
    threshold_used = Column(Float, nullable=True)

    # Individual layer scores
    rule_score = Column(Float, nullable=True)
    stats_score = Column(Float, nullable=True)
    ml_score = Column(Float, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    ensemble_score = Column(Float, nullable=True)

    # Reasoning
    reasoning = Column(Text, nullable=True)
    signals_json = Column(JSON, nullable=True)  # All signals that contributed

    # Outcome (filled after trade closes)
    trade_id = Column(Integer, nullable=True)
    was_profitable = Column(Boolean, nullable=True)


class Signal(Base):
    """Individual analysis signals."""
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=utcnow, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    source = Column(String(50), nullable=False)  # RSI_H1, MACD_D1, NEWS_USD, ML_MODEL
    direction = Column(String(10), nullable=False)  # BUY, SELL, NEUTRAL
    strength = Column(Float, nullable=False)  # 0.0 to 1.0
    confidence = Column(Float, nullable=True)
    timeframe = Column(String(10), nullable=True)
    reasoning = Column(Text, nullable=True)
    data_json = Column(JSON, nullable=True)


class AccountSnapshot(Base):
    """Periodic snapshots of account state for tracking."""
    __tablename__ = "account_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=utcnow, index=True)
    balance = Column(Float, nullable=False)
    equity = Column(Float, nullable=False)
    margin = Column(Float, nullable=True)
    free_margin = Column(Float, nullable=True)
    open_positions = Column(Integer, default=0)
    daily_pnl = Column(Float, nullable=True)
    peak_equity = Column(Float, nullable=True)
    drawdown_pct = Column(Float, nullable=True)


class NewsEvent(Base):
    """Cached news events and their sentiment."""
    __tablename__ = "news_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=utcnow, index=True)
    title = Column(String(500), nullable=False)
    source = Column(String(100), nullable=True)
    url = Column(String(500), nullable=True)
    currencies_affected = Column(String(100), nullable=True)  # comma-separated
    sentiment_score = Column(Float, nullable=True)  # -1.0 to +1.0
    impact = Column(String(20), nullable=True)  # high, medium, low
    analysis = Column(Text, nullable=True)


class TradingHours(Base):
    """Trading hours configuration for the bot."""
    __tablename__ = "trading_hours"

    id = Column(Integer, primary_key=True, autoincrement=True)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    open_time = Column(String(5), nullable=False, default="00:00")  # HH:MM
    close_time = Column(String(5), nullable=False, default="23:59")  # HH:MM
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
