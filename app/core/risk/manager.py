"""
Risk Manager — Ensures all trading parameters comply with strict risk rules.
"""
from typing import Dict, Any, List
from app.config import settings
from app.utils.logger import logger


class RiskManager:
    """Evaluates whether to allow a trade based on predefined rules."""

    def __init__(self):
        self.daily_limit = settings.max_daily_loss_pct
        self.weekly_limit = settings.max_weekly_loss_pct
        self.max_exposure = settings.max_open_positions
        self.drawdown_limit = settings.drawdown_circuit_breaker_pct

    def check_trade_allowed(
        self,
        symbol: str,
        direction: str,
        account_info: Dict[str, Any],
        open_positions: List[Dict[str, Any]],
        daily_pnl: float,
        weekly_pnl: float,
        peak_equity: float,
    ) -> Dict[str, Any]:
        """
        Runs all risk checks before allowing a trade to execute.
        Returns {"allowed": True/False, "reason": ""}
        """
        equity = account_info.get("equity", 0)
        if equity <= 0:
            return {"allowed": False, "reason": "Account equity zero or not loaded"}

        # Check 1: Max Open Positions
        if len(open_positions) >= settings.max_open_positions:
            return {"allowed": False, "reason": f"Max open positions reached ({settings.max_open_positions})"}

        # Check 2: Already holding this currency pair?
        if not settings.allow_multiple_per_pair:
            symbols_held = [p.get("symbol", "") for p in open_positions]
            if symbol in symbols_held:
                # Simple rule: 1 position per pair at a time max
                return {"allowed": False, "reason": f"Already holding {symbol}"}

        # Check 2.5: Correlation exposure
        base_ccy = symbol[:3]
        quote_ccy = symbol[3:]
        for p in open_positions:
            s_held = p.get("symbol", "")
            if len(s_held) >= 6:
                held_base = s_held[:3]
                held_quote = s_held[3:]
                held_dir = "BUY" if "BUY" in str(p.get("type", "")).upper() else "SELL"
                
                # Same-direction exposure on same currency (skip if it's the exact same pair, handled in Check 2)
                if s_held != symbol and (base_ccy == held_base or quote_ccy == held_quote) and held_dir == direction:
                    return {"allowed": False, "reason": f"Correlated exposure: already {held_dir} {s_held}"}

        # Check 3: Daily PNL Limit
        daily_pnl_pct = (daily_pnl / equity) * 100
        if daily_pnl_pct <= -self.daily_limit:
            return {"allowed": False, "reason": f"Daily loss limit hit ({daily_pnl_pct:.2f}% <= -{self.daily_limit}%)"}

        # Check 4: Weekly PNL Limit
        weekly_pnl_pct = (weekly_pnl / equity) * 100
        if weekly_pnl_pct <= -self.weekly_limit:
            return {"allowed": False, "reason": f"Weekly loss limit hit ({weekly_pnl_pct:.2f}% <= -{self.weekly_limit}%)"}

        # Check 5: Drawdown Circuit Breaker
        if peak_equity > 0:
            drawdown_pct = ((peak_equity - equity) / peak_equity) * 100
            if drawdown_pct >= self.drawdown_limit:
                logger.critical(f"🚨 CIRCUIT BREAKER: Drawdown {drawdown_pct:.2f}% exceeds {self.drawdown_limit}%")
                return {"allowed": False, "reason": f"Drawdown circuit breaker triggered ({drawdown_pct:.2f}%)"}

        # Check 6: Margin Available
        free_margin = account_info.get("free_margin", 0)
        # Assuming we need at least 5% of equity free to comfortably trade
        if free_margin < (equity * 0.05):
            return {"allowed": False, "reason": "Insufficient free margin padding"}

        return {"allowed": True, "reason": "Risk checks passed"}


# Singleton
risk_manager = RiskManager()
