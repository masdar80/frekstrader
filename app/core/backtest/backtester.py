import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import pandas as pd

from app.config import settings
from app.utils.logger import logger
from app.core.broker.metaapi_client import broker
from app.core.analysis.technical import technical_analyzer
from app.core.analysis.signals import normalize_technical_signals
from app.core.brain.decision_engine import decision_engine
from app.core.backtest.backtest_result import BacktestResult, BacktestTrade

class Backtester:
    """High-Fidelity Historical Replay Engine."""

    def __init__(self):
        self.initial_balance = 200.0
        self.open_trades = []
        self.closed_trades = []

    async def run(self, symbol: str, days: int = 90) -> BacktestResult:
        """Run historical backtest with Multi-Trade and Trailing SL support."""
        logger.info(f"💾 Starting High-Fidelity Backtest for {symbol} ({days} days)...")
        
        # 1. Reset state
        self.open_trades = []
        self.closed_trades = []
        balance = self.initial_balance
        equity = balance
        
        # 2. Fetch Symbol Info
        symbol_info = await broker.get_symbol_info(symbol)
        digits = symbol_info.get("digits", 5)
        point = symbol_info.get("point", 0.00001)
        contract_size = symbol_info.get("contract_size", 100000)
        is_jpy = "JPY" in symbol
        
        # Pre-fetch data
        candle_data = {}
        tfs = ["15m", "1h", "4h", "1d"]
        
        for tf in tfs:
            candles = await broker.get_candles(symbol, timeframe=tf, count=2000)
            if not candles: return None
            df = pd.DataFrame(candles)
            df["time"] = pd.to_datetime(df["time"])
            df.set_index("time", inplace=True)
            df.sort_index(inplace=True)
            candle_data[tf] = df

        replay_df = candle_data["1h"]
        result = BacktestResult(
            symbol=symbol,
            start_date=replay_df.index[0].isoformat(),
            end_date=replay_df.index[-1].isoformat(),
            trading_mode=settings.trading_mode.value
        )
        
        # settings cache
        max_pos = settings.max_open_positions
        trail_enabled = settings.trailing_stop_enabled
        be_mult = settings.trailing_breakeven_atr_mult
        trail_mult = settings.trailing_atr_mult

        # 3. Main Replay Loop
        for i in range(100, len(replay_df)):
            current_time = replay_df.index[i]
            current_bar = replay_df.iloc[i]
            current_price = current_bar["close"]
            
            # Update Floating PnL & Equity
            floating_pnl = self._calculate_unrealized_pnl(current_price, point, contract_size, is_jpy)
            equity = balance + floating_pnl
            
            if equity <= 0:
                result.equity_curve.append({"time": current_time.isoformat(), "equity": 0})
                break
            result.equity_curve.append({"time": current_time.isoformat(), "equity": round(equity, 2)})
            
            # Manage Trades (SL/TP/Trailing)
            trades_to_close = self._manage_open_trades(
                current_time, current_bar, point, contract_size, is_jpy,
                trail_enabled, be_mult, trail_mult
            )
            for t in trades_to_close:
                balance += t.profit
                self.closed_trades.append(t)

            # Analyze & Execute
            if len(self.open_trades) < max_pos:
                sliced_candles = {}
                for tf, df_tf in candle_data.items():
                    df_slice = df_tf[df_tf.index <= current_time].tail(200)
                    sliced_candles[tf] = df_slice.reset_index().to_dict('records')

                ta_results = technical_analyzer.analyze(sliced_candles)
                ta_confluence = technical_analyzer.get_confluence_score(ta_results)
                signal = normalize_technical_signals(symbol, ta_confluence)
                decision = decision_engine.evaluate_signals(symbol, [signal])
                
                if decision.action in ["BUY", "SELL"]:
                    # Risk Math
                    risk_pct = settings.effective_max_risk_pct / 100.0
                    risk_amount = min(balance * risk_pct, settings.max_risk_amount_usd)
                    
                    atr_val = ta_results["ATR"][-1].value if "ATR" in ta_results else (point * 15)
                    dist_sl = atr_val * 2.0  # User manual setting
                    sl_points = dist_sl / point
                    
                    tick_val_usd = (point * contract_size)
                    if is_jpy: tick_val_usd = tick_val_usd / current_price
                    
                    volume = max(0.01, round(risk_amount / (sl_points * tick_val_usd), 2))
                    
                    is_buy = decision.action == "BUY"
                    sl_price = round(current_price - dist_sl if is_buy else current_price + dist_sl, digits)
                    tp_price = round(current_price + (dist_sl * 2) if is_buy else current_price - (dist_sl * 2), digits)
                    
                    self.open_trades.append({
                        "symbol": symbol,
                        "direction": decision.action,
                        "open_time": current_time,
                        "open_price": current_price,
                        "sl": sl_price,
                        "tp": tp_price,
                        "volume": volume,
                        "atr": atr_val,
                        "highest_price": current_price if is_buy else 999999,
                        "lowest_price": current_price if not is_buy else 0
                    })

        result.trades = self.closed_trades
        result.calculate_metrics(self.initial_balance)
        return result

    def _calculate_unrealized_pnl(self, current_price: float, point: float, contract_size: float, is_jpy: bool) -> float:
        pnl = 0.0
        for t in self.open_trades:
            diff = (current_price - t["open_price"]) if t["direction"] == "BUY" else (t["open_price"] - current_price)
            tick_val = (point * contract_size)
            if is_jpy: tick_val = tick_val / current_price
            pnl += (diff / point) * tick_val * t["volume"]
        return pnl

    def _manage_open_trades(self, time, bar, point, contract_size, is_jpy, trail_on, be_mult, trail_mult) -> List[BacktestTrade]:
        high, low, close = bar["high"], bar["low"], bar["close"]
        closed, remaining = [], []
        
        for t in self.open_trades:
            hit_tp, hit_sl = False, False
            is_buy = t["direction"] == "BUY"
            
            # 1. Update Trade High/Low for Trailing
            if is_buy: t["highest_price"] = max(t["highest_price"], high)
            else: t["lowest_price"] = min(t["lowest_price"], low)
            
            # 2. Check Static SL/TP
            if is_buy:
                if high >= t["tp"]: hit_tp = True
                elif low <= t["sl"]: hit_sl = True
            else:
                if low <= t["tp"]: hit_tp = True
                elif high >= t["sl"]: hit_sl = True
            
            # 3. Trailing Stop & Breakeven Logic
            if not hit_tp and not hit_sl and trail_on:
                current_profit_points = (close - t["open_price"]) / point if is_buy else (t["open_price"] - close) / point
                atr_points = t["atr"] / point
                
                # Breakeven
                if be_mult > 0 and current_profit_points >= (atr_points * be_mult):
                    if is_buy and t["sl"] < t["open_price"]: t["sl"] = t["open_price"]
                    elif not is_buy and t["sl"] > t["open_price"]: t["sl"] = t["open_price"]
                
                # Dynamic Trailing
                if trail_mult > 0:
                    dist = t["atr"] * trail_mult
                    if is_buy:
                        new_sl = t["highest_price"] - dist
                        if new_sl > t["sl"]: t["sl"] = new_sl
                    else:
                        new_sl = t["lowest_price"] + dist
                        if new_sl < t["sl"]: t["sl"] = new_sl

            # 4. Final Finalize
            if hit_tp or hit_sl:
                exit_p = t["tp"] if hit_tp else t["sl"]
                diff = (exit_p - t["open_price"]) if is_buy else (t["open_price"] - exit_p)
                tick_v = (point * contract_size)
                if is_jpy: tick_v = tick_v / t["open_price"]
                profit = (diff / point) * tick_v * t["volume"]
                
                closed.append(BacktestTrade(
                    symbol=t["symbol"], direction=t["direction"],
                    open_time=t["open_time"], close_time=time,
                    open_price=t["open_price"], close_price=exit_p,
                    volume=t["volume"], profit=round(profit, 2),
                    pnl_pct=round((profit / self.initial_balance) * 100, 2),
                    exit_reason="TP" if hit_tp else "SL"
                ))
            else:
                remaining.append(t)
        
        self.open_trades = remaining
        return closed

backtester = Backtester()
