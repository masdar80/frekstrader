import pandas as pd
from typing import Dict, List, Any
import uuid

from app.data.candle_store import candle_store
from app.core.analysis.technical import technical_analyzer
from app.core.analysis.regime import regime_detector
from app.core.analysis.signals import normalize_technical_signals, StandardSignal
from app.core.brain.decision_engine import decision_engine
from app.config import settings
from app.utils.logger import logger

class BacktestTrade:
    def __init__(self, symbol: str, direction: str, entry_price: float, sl: float, tp: float, atr: float, open_time: pd.Timestamp):
        self.id = str(uuid.uuid4())
        self.symbol = symbol
        self.direction = direction
        self.entry_price = entry_price
        self.sl = sl
        self.tp = tp
        self.atr = atr
        self.open_time = open_time
        self.close_time = None
        self.close_price = None
        self.close_reason = None
        self.profit_pips = 0.0

class Backtester:
    def __init__(self, symbol: str, start_dt: str, end_dt: str, initial_balance=1000.0, spread_pips=1.5):
        self.symbol = symbol
        self.start_dt = pd.to_datetime(start_dt)
        self.end_dt = pd.to_datetime(end_dt)
        self.balance = initial_balance
        self.spread_pips = spread_pips
        self.trades: List[BacktestTrade] = []
        self.open_trades: List[BacktestTrade] = []
        
        self.pip_size = 0.01 if "JPY" in symbol else 0.0001
        self.spread_val = self.spread_pips * self.pip_size
        
        # Load data
        logger.info(f"Loading backtest data for {symbol}...")
        self.df_15m = candle_store.get_slice(symbol, "15m", start_dt, end_dt)
        self.df_1h = candle_store.get_slice(symbol, "1h", start_dt, end_dt)
        self.df_4h = candle_store.get_slice(symbol, "4h", start_dt, end_dt)
        self.df_1d = candle_store.get_slice(symbol, "1d", start_dt, end_dt)
        
        # Precompute
        self.df_15m = technical_analyzer.precompute(self.df_15m)
        self.df_1h = technical_analyzer.precompute(self.df_1h)
        self.df_4h = technical_analyzer.precompute(self.df_4h)
        self.df_1d = technical_analyzer.precompute(self.df_1d)
        
        self.df_by_tf = {
            "15m": self.df_15m,
            "1h": self.df_1h,
            "4h": self.df_4h,
            "1d": self.df_1d
        }

    def _check_stops(self, trade: BacktestTrade, high: float, low: float, current_time: pd.Timestamp) -> bool:
        """Checks if SL or TP is hit. Returns True if trade closed."""
        closed = False
        if trade.direction == "BUY":
            if low <= trade.sl:
                trade.close_price = trade.sl
                trade.close_reason = "SL"
                closed = True
            elif high >= trade.tp:
                trade.close_price = trade.tp
                trade.close_reason = "TP"
                closed = True
        else: # SELL
            if high >= trade.sl:
                trade.close_price = trade.sl
                trade.close_reason = "SL"
                closed = True
            elif low <= trade.tp:
                trade.close_price = trade.tp
                trade.close_reason = "TP"
                closed = True
                
        if closed:
            trade.close_time = current_time
            if trade.direction == "BUY":
                trade.profit_pips = (trade.close_price - trade.entry_price) / self.pip_size
            else:
                trade.profit_pips = (trade.entry_price - trade.close_price) / self.pip_size
            self.trades.append(trade)
            
        return closed

    def _update_trailing_stops(self, current_price: float):
        for trade in self.open_trades:
            if not settings.trailing_stop_enabled:
                continue
                
            atr_val = trade.atr
            is_buy = trade.direction == "BUY"
            
            profit_dist = (current_price - trade.entry_price) if is_buy else (trade.entry_price - current_price)
            be_threshold = atr_val * settings.trailing_breakeven_atr_mult
            
            at_breakeven = False
            if trade.sl:
                if is_buy:
                    at_breakeven = (trade.sl >= trade.entry_price)
                else:
                    at_breakeven = (trade.sl <= trade.entry_price)
                    
            new_sl = None
            if not at_breakeven and profit_dist >= be_threshold:
                new_sl = trade.entry_price
                
            if at_breakeven:
                profit_in_atr = profit_dist / atr_val if atr_val > 0 else 0
                current_mult = settings.trailing_atr_mult
                
                if profit_in_atr > 3.0:
                    current_mult = max(0.5, current_mult - 1.0)
                elif profit_in_atr > 2.0:
                    current_mult = max(1.0, current_mult - 0.5)
                    
                trail_dist = atr_val * current_mult
                target_sl = (current_price - trail_dist) if is_buy else (current_price + trail_dist)
                
                if is_buy:
                    if target_sl > trade.sl:
                        new_sl = max(target_sl, trade.entry_price)
                else:
                    if target_sl < trade.sl:
                        new_sl = min(target_sl, trade.entry_price)
                        
            if new_sl:
                trade.sl = new_sl

    def run(self) -> Dict[str, Any]:
        logger.info("Starting Backtest...")
        
        # Iterate over 15m candles
        for current_time, row in self.df_15m.iterrows():
            # 1. Manage open positions (check SL/TP using OHLC of current candle)
            high, low = row["high"], row["low"]
            close = row["close"]
            
            still_open = []
            for trade in self.open_trades:
                if not self._check_stops(trade, high, low, current_time):
                    still_open.append(trade)
            self.open_trades = still_open
            
            # 2. Update trailing stops based on close price
            self._update_trailing_stops(close)
            
            # 3. Decision making (only if no open trades, to simplify)
            if len(self.open_trades) < settings.max_open_positions:
                ta_raw_results = technical_analyzer.analyze_row(self.df_by_tf, current_time)
                ta_confluence = technical_analyzer.get_confluence_score(ta_raw_results)
                
                regime_info = regime_detector.detect(self.symbol, ta_raw_results)
                
                tech_sig = StandardSignal(
                    symbol=self.symbol,
                    source="TECH_CONFLUENCE",
                    direction=ta_confluence["direction"],
                    strength=ta_confluence["confidence"],
                    confidence=ta_confluence["confidence"],
                    reasoning=f"Confluence: buy_votes={ta_confluence['buy_votes']}, sell_votes={ta_confluence['sell_votes']}",
                    metadata={"breakdown": ta_confluence["breakdown"]}
                )
                
                decision = decision_engine.evaluate_signals_with_config(
                    self.symbol, [tech_sig], settings.confidence_threshold, regime_info=regime_info
                )    
                if decision.action in ["BUY", "SELL"]:
                    # Get ATR for SL/TP
                    atr_1h = 0.0010
                    if "ATR" in ta_raw_results:
                        for res in ta_raw_results["ATR"]:
                            if res.timeframe == "1h":
                                atr_1h = res.details.get("atr", 0.0010)
                                break
                                
                    # Calculate entry price with spread
                    entry_price = close + self.spread_val if decision.action == "BUY" else close - self.spread_val
                    
                    sl_dist = atr_1h * settings.risk_atr_mult_sl
                    tp_dist = atr_1h * settings.risk_atr_mult_tp
                    
                    if decision.action == "BUY":
                        sl = entry_price - sl_dist
                        tp = entry_price + tp_dist
                    else:
                        sl = entry_price + sl_dist
                        tp = entry_price - tp_dist
                        
                    new_trade = BacktestTrade(
                        symbol=self.symbol,
                        direction=decision.action,
                        entry_price=entry_price,
                        sl=sl,
                        tp=tp,
                        atr=atr_1h,
                        open_time=current_time
                    )
                    self.open_trades.append(new_trade)
                    
        # Close remaining trades at end
        final_close = self.df_15m.iloc[-1]["close"]
        final_time = self.df_15m.index[-1]
        for trade in self.open_trades:
            trade.close_price = final_close
            trade.close_time = final_time
            trade.close_reason = "END_OF_TEST"
            if trade.direction == "BUY":
                trade.profit_pips = (trade.close_price - trade.entry_price) / self.pip_size
            else:
                trade.profit_pips = (trade.entry_price - trade.close_price) / self.pip_size
            self.trades.append(trade)
            
        return self._generate_report()
        
    def _generate_report(self) -> Dict[str, Any]:
        wins = [t for t in self.trades if t.profit_pips > 0]
        losses = [t for t in self.trades if t.profit_pips <= 0]
        total_pips = sum(t.profit_pips for t in self.trades)
        
        return {
            "total_trades": len(self.trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(self.trades) if self.trades else 0,
            "total_pips": round(total_pips, 2),
            "trade_pips": [t.profit_pips for t in self.trades]
        }
