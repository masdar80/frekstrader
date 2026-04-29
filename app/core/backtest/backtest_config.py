from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class BacktestConfig:
    """All tunable parameters for a single backtest run."""
    # Identity
    name: str = "default"
    
    # Trading mode thresholds
    confidence_threshold: float = 0.45
    min_indicators: int = 3
    
    # Risk
    max_risk_pct: float = 1.5
    max_risk_amount_usd: float = 20.0
    max_open_positions: int = 5
    allow_multiple_per_pair: bool = False
    
    # SL/TP geometry
    sl_atr_multiplier: float = 2.0       # SL distance = ATR × this
    tp_rr_ratio: float = 2.0             # TP distance = SL distance × this
    
    # Trailing stop
    trailing_stop_enabled: bool = True
    trailing_breakeven_atr_mult: float = 1.0
    trailing_atr_mult: float = 1.5
    
    # Signal weights
    tech_weight: float = 1.0             # Weight for TECH_CONFLUENCE (1.0 when sentiment off)
    
    # Portfolio
    initial_balance: float = 200.0
    use_correlation_filter: bool = False  # OFF per user request
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}
