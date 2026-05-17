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
        current_price: float = 0.0,
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
        same_pair_positions = [p for p in open_positions if p.get("symbol", "") == symbol]
        if same_pair_positions:
            if not settings.allow_multiple_per_pair:
                # Simple rule: 1 position per pair at a time max
                return {"allowed": False, "reason": f"Already holding {symbol}"}
            else:
                # Anti-Spam Check: Cooldown and Distance
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                is_jpy = "JPY" in symbol
                pip_multiplier = 100 if is_jpy else 10000
                
                for p in same_pair_positions:
                    # Time Check
                    open_time_str = p.get("open_time")
                    if open_time_str:
                        try:
                            # Parse '2024-03-24T18:00:00.000Z'
                            open_time = datetime.fromisoformat(open_time_str.replace("Z", "+00:00"))
                            hours_since = (now - open_time).total_seconds() / 3600
                            if hours_since < getattr(settings, "multi_pair_cooldown_hours", 4.0):
                                return {"allowed": False, "reason": f"Cooldown active for {symbol} ({hours_since:.1f}h < {getattr(settings, 'multi_pair_cooldown_hours', 4.0)}h)"}
                        except Exception as e:
                            logger.error(f"Error parsing time for cooldown check: {e}")
                    
                    # Distance Check
                    open_price = p.get("openPrice") or p.get("price") or 0.0
                    if open_price > 0 and current_price > 0:
                        dist_pips = abs(current_price - open_price) * pip_multiplier
                        min_dist = getattr(settings, "multi_pair_min_distance_pips", 10.0)
                        if dist_pips < min_dist:
                            return {"allowed": False, "reason": f"Distance too close for {symbol} ({dist_pips:.1f} pips < {min_dist} pips)"}

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
