from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime

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
    
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    trades: List[BacktestTrade] = field(default_factory=list)

    def calculate_metrics(self, initial_balance: float):
        """Finalize metrics after the run."""
        if not self.trades:
            return
            
        self.total_trades = len(self.trades)
        self.winning_trades = len([t for t in self.trades if t.profit > 0])
        self.losing_trades = self.total_trades - self.winning_trades
        self.win_rate = (self.winning_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
        
        gross_profit = sum([t.profit for t in self.trades if t.profit > 0])
        gross_loss = abs(sum([t.profit for t in self.trades if t.profit < 0]))
        
        self.profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
        self.total_profit = gross_profit - gross_loss
        self.avg_trade_pnl = self.total_profit / self.total_trades if self.total_trades > 0 else 0
        
        # Drawdown calculation
        peak = initial_balance
        max_dd = 0
        current_balance = initial_balance
        
        for point in self.equity_curve:
            current_balance = point["equity"]
            if current_balance > peak:
                peak = current_balance
            
            dd = ((peak - current_balance) / peak) * 100
            if dd > max_dd:
                max_dd = dd
        
        self.max_drawdown = round(max_dd, 2)
        self.total_profit = round(self.total_profit, 2)
        self.win_rate = round(self.win_rate, 2)
        self.profit_factor = round(self.profit_factor, 2)

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "trading_mode": self.trading_mode,
            "summary": {
                "total_trades": self.total_trades,
                "win_rate": self.win_rate,
                "total_profit": self.total_profit,
                "max_drawdown": self.max_drawdown,
                "profit_factor": self.profit_factor,
                "avg_trade_pnl": self.avg_trade_pnl
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
                    "profit": t.profit
                } for t in self.trades
            ]
        }
