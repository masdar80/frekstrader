"""
ForeksTrader Configuration
Loads settings from .env and provides typed access to all configuration.
"""
import os
from enum import Enum
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class TradingMode(str, Enum):
    ULTRA_CONSERVATIVE = "ultra_conservative"
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    ULTRA_AGGRESSIVE = "ultra_aggressive"


# Trading mode presets: (confidence_threshold, max_risk_pct, min_indicators_agree)
TRADING_MODE_PRESETS = {
    TradingMode.ULTRA_CONSERVATIVE: {"confidence_threshold": 0.75, "max_risk_pct": 0.5, "min_indicators": 5},
    TradingMode.CONSERVATIVE:       {"confidence_threshold": 0.60, "max_risk_pct": 1.0, "min_indicators": 4},
    TradingMode.BALANCED:           {"confidence_threshold": 0.45, "max_risk_pct": 1.5, "min_indicators": 3},
    TradingMode.AGGRESSIVE:         {"confidence_threshold": 0.35, "max_risk_pct": 2.5, "min_indicators": 2},
    TradingMode.ULTRA_AGGRESSIVE:   {"confidence_threshold": 0.25, "max_risk_pct": 4.0, "min_indicators": 1},
}


class Settings(BaseSettings):
    # === MetaAPI ===
    metaapi_token: str = ""
    metaapi_account_id: str = ""

    # === MT5 ===
    mt5_login: str = ""
    mt5_server: str = ""
    mt5_password: str = ""

    # === Database ===
    database_url: str = "postgresql+asyncpg://foreks:foreks_secret@localhost:5432/foreksdb"

    # === Redis ===
    redis_url: str = "redis://localhost:6379/0"

    # === News API ===
    news_api_key: str = ""

    # === Gemini AI ===
    gemini_api_key: str = ""

    # === Trading ===
    trading_pairs: str = "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCHF"
    trading_mode: TradingMode = TradingMode.BALANCED
    use_ai_sentiment: bool = True

    # === Risk Management ===
    max_risk_per_trade_pct: float = 1.5
    max_daily_loss_pct: float = 3.0
    max_weekly_loss_pct: float = 7.0
    max_open_positions: int = 3
    max_drawdown_pct: float = 10.0
    news_blackout_minutes: int = 30
    drawdown_circuit_breaker_pct: float = 10.0
    max_slippage_pips: float = 3.0
    max_risk_amount_usd: float = 20.0  # Phase 1.3: Hard cap on trade loss

    # === Trailing Stop Loss (Phase 2) ===
    trailing_stop_enabled: bool = True
    trailing_breakeven_atr_mult: float = 1.0  # Move SL to breakeven at 1.0x ATR profit
    trailing_atr_mult: float = 1.5           # Trail behind price at 1.5x ATR distance

    # === Server ===
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False
    app_api_key: str = ""
    allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def pairs_list(self) -> List[str]:
        return [p.strip() for p in self.trading_pairs.split(",")]

    @property
    def mode_preset(self) -> dict:
        return TRADING_MODE_PRESETS[self.trading_mode]

    @property
    def confidence_threshold(self) -> float:
        return self.mode_preset["confidence_threshold"]

    @property
    def min_indicators_required(self) -> int:
        return self.mode_preset["min_indicators"]

    @property
    def effective_max_risk_pct(self) -> float:
        return self.mode_preset["max_risk_pct"]


settings = Settings()
