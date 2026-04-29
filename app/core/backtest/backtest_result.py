from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime
import numpy as np

@dataclass
class BacktestTrade:
    symbol: str
    direction: str
    open_time: datetime
    close_time: datetime
    open_price: float
    close_price: float
    volume: float
    profit: float
    pnl_pct: float
    exit_reason: str # TP, SL, TIMEOUT

@dataclass
class BacktestResult:
    symbol: str
    start_date: str
    end_date: str
    trading_mode: str
    
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    total_profit: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    avg_trade_pnl: float = 0.0

    # New Metrics
    sharpe_ratio: float = 0.0
    max_consecutive_losses: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    return_pct: float = 0.0
    config_name: str = ""
    config_dict: Dict[str, Any] = field(default_factory=list) # Default as list or dict? Usually config is dict. Fixed below.
    
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    trades: List[BacktestTrade] = field(default_factory=list)

    def calculate_metrics(self, initial_balance: float):
        """Finalize metrics after the run."""
        if not self.trades:
            return
            
        self.total_trades = len(self.trades)
        wins = [t for t in self.trades if t.profit > 0]
        losses = [t for t in self.trades if t.profit <= 0]
        
        self.winning_trades = len(wins)
        self.losing_trades = self.total_trades - self.winning_trades
        self.win_rate = (self.winning_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
        
        gross_profit = sum([t.profit for t in wins])
        gross_loss = abs(sum([t.profit for t in losses]))
        
        self.avg_win = gross_profit / self.winning_trades if self.winning_trades > 0 else 0
        self.avg_loss = gross_loss / self.losing_trades if self.losing_trades > 0 else 0
        
        self.profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
        self.total_profit = gross_profit - gross_loss
        self.avg_trade_pnl = self.total_profit / self.total_trades if self.total_trades > 0 else 0
        self.return_pct = (self.total_profit / initial_balance) * 100 if initial_balance > 0 else 0
        
        # Max consecutive losses
        max_cons_losses = 0
        current_cons = 0
        for t in self.trades:
            if t.profit <= 0:
                current_cons += 1
                max_cons_losses = max(max_cons_losses, current_cons)
            else:
                current_cons = 0
        self.max_consecutive_losses = max_cons_losses
        
        # Drawdown and Sharpe Ratio calculation
        peak = initial_balance
        max_dd = 0
        
        equities = [initial_balance] + [p["equity"] for p in self.equity_curve]
        
        for eq in equities:
            if eq > peak:
                peak = eq
            dd = ((peak - eq) / peak) * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        self.max_drawdown = round(max_dd, 2)
        
        # Simple Daily Sharpe (estimated from 1h bars)
        if len(equities) > 24:
            # Group into 24h chunks for "daily" returns
            daily_equities = equities[::24]
            returns = []
            for i in range(1, len(daily_equities)):
                prev = daily_equities[i-1]
                curr = daily_equities[i]
                if prev > 0:
                    returns.append((curr - prev) / prev)
            
            if returns and np.std(returns) > 0:
                avg_ret = np.mean(returns)
                std_ret = np.std(returns)
                self.sharpe_ratio = round((avg_ret / std_ret) * np.sqrt(252), 3)

        self.total_profit = round(self.total_profit, 2)
        self.win_rate = round(self.win_rate, 2)
        self.profit_factor = round(self.profit_factor, 2)

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "config_name": self.config_name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "trading_mode": self.trading_mode,
            "summary": {
                "total_trades": self.total_trades,
                "win_rate": self.win_rate,
                "total_profit": self.total_profit,
                "return_pct": round(self.return_pct, 2),
                "max_drawdown": self.max_drawdown,
                "profit_factor": self.profit_factor,
                "avg_trade_pnl": round(self.avg_trade_pnl, 2),
                "sharpe_ratio": self.sharpe_ratio,
                "max_cons_losses": self.max_consecutive_losses,
                "avg_win": round(self.avg_win, 2),
                "avg_loss": round(self.avg_loss, 2)
            },
            "equity_curve": self.equity_curve,
            "trades": [
                {
                    "symbol": t.symbol,
                    "direction": t.direction,
                    "open_time": t.open_time.isoformat(),
                    "close_time": t.close_time.isoformat(),
                    "open_price": t.open_price,
                    "close_price": t.close_price,
                    "volume": t.volume,
                    "profit": t.profit,
                    "exit_reason": t.exit_reason
                } for t in self.trades
            ]
        }

