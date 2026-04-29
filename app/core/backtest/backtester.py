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
    """High-Fidelity Portfolio Replay Engine (Simultaneous Symbols)."""

    def __init__(self):
        self.initial_balance = 200.0
        self.open_trades = []
        self.closed_trades = []

    async def run_portfolio(self, symbols: List[str], days: int = 90, config: Any = None, candle_cache: Dict[str, Any] = None) -> (BacktestResult, Dict[str, Any]):
        """Run a synchronized replay of multiple symbols with config overrides."""
        if config is None:
            from app.core.backtest.backtest_config import BacktestConfig
            config = BacktestConfig()
            
        logger.info(f"Starting Backtest '{config.name}' for {symbols}...")
        
        # Reset state
        self.open_trades = []
        self.closed_trades = []
        balance = config.initial_balance
        self.initial_balance = balance
        
        # 1. Fetch Symbol Data & Find Common Timeframe (or use cache)
        candle_data = candle_cache if candle_cache else {}
        symbol_meta = {}
        
        for symbol in symbols:
            info = await broker.get_symbol_info(symbol)
            symbol_meta[symbol] = {
                "digits": info.get("digits", 5),
                "point": info.get("point", 0.00001),
                "contract_size": info.get("contract_size", 100000),
                "is_jpy": "JPY" in symbol
            }
            
            if not candle_cache:
                logger.info(f"  Fetching candles for {symbol}...")
                symbol_candles = {}
                
                # Fetch timeframes with small delays to avoid 429
                for tf in ["1h", "15m", "4h", "1d"]:
                    for attempt in range(3):
                        candles = await broker.get_candles(symbol, timeframe=tf, count=2000)
                        if candles:
                            df = pd.DataFrame(candles)
                            if not df.empty and "time" in df.columns:
                                df["time"] = pd.to_datetime(df["time"])
                                df.set_index("time", inplace=True)
                                symbol_candles[tf] = df
                                break
                        
                        logger.warning(f"    [!] Failed to fetch {tf} for {symbol} (attempt {attempt+1}/3). Retrying...")
                        await asyncio.sleep(5)
                    
                    await asyncio.sleep(1) # Gap between timeframes
                
                if "1h" in symbol_candles:
                    # Precompute indicators for all timeframes
                    for tf in symbol_candles:
                        symbol_candles[tf] = technical_analyzer.precompute(symbol_candles[tf])
                    candle_data[symbol] = symbol_candles
                
                await asyncio.sleep(2) # Gap between symbols

        # 2. Get the Replay Clock (Union of all symbols' 1h timestamps)
        all_times = pd.Index([])
        for symbol in symbols:
            if symbol in candle_data:
                all_times = all_times.union(candle_data[symbol]["1h"].index)
        
        if all_times.empty:
            logger.error("No candle data fetched. Backtest aborted.")
            return None, candle_data
            
        all_times = sorted(all_times)[-days*24:] # Limit to requested days
        
        result = BacktestResult(
            symbol="PORTFOLIO",
            start_date=all_times[0].isoformat(),
            end_date=all_times[-1].isoformat(),
            trading_mode=config.name,
            config_name=config.name,
            config_dict=config.to_dict()
        )
        
        # 3. Synchronized Replay Loop
        for current_time in all_times:
            # A. Update Trading Management for all symbols
            for symbol in symbols:
                if symbol not in candle_data: continue
                df_clock = candle_data[symbol]["1h"]
                if current_time not in df_clock.index: continue
                
                meta = symbol_meta[symbol]
                bar = df_clock.loc[current_time]
                
                # Check Closures & Manage Trailing
                trades_to_close = self._manage_trades_for_symbol(
                    symbol, current_time, bar, meta,
                    config.trailing_stop_enabled,
                    config.trailing_breakeven_atr_mult,
                    config.trailing_atr_mult
                )
                for t in trades_to_close:
                    balance += t.profit
                    self.closed_trades.append(t)
            
            # B. Update Equity Curve
            current_prices = {}
            for s in symbols:
                 if s in candle_data and current_time in candle_data[s]["1h"].index:
                     current_prices[s] = candle_data[s]["1h"].loc[current_time]["close"]
            
            floating_pnl = self._calculate_overall_unrealized(current_prices, symbol_meta)
            equity = balance + floating_pnl
            result.equity_curve.append({"time": current_time.isoformat(), "equity": round(equity, 2)})

            # C. Check for new entries for each symbol
            if len(self.open_trades) < config.max_open_positions:
                for symbol in symbols:
                    if symbol not in candle_data or current_time not in candle_data[symbol]["1h"].index: 
                        continue
                    
                    # Ensure we don't double-dip on the same symbol unless allowed
                    if not config.allow_multiple_per_pair and any(t["symbol"] == symbol for t in self.open_trades):
                        continue

                    # Fast Analysis using precomputed row
                    ta_results = technical_analyzer.analyze_row(candle_data[symbol], current_time)
                    ta_confluence = technical_analyzer.get_confluence_score(ta_results)
                    signal = normalize_technical_signals(symbol, ta_confluence)
                    
                    # USE CONFIG OVERRIDES FOR BRAIN
                    decision = decision_engine.evaluate_signals_with_config(
                        symbol, [signal], 
                        confidence_threshold=config.confidence_threshold,
                        tech_weight=config.tech_weight
                    )
                    
                    if decision.action in ["BUY", "SELL"]:
                        meta = symbol_meta[symbol]
                        cur_p = current_prices[symbol]
                        
                        # Risk Math
                        risk_pct = config.max_risk_pct / 100.0
                        risk_amount = min(balance * risk_pct, config.max_risk_amount_usd)
                        
                        atr_val = ta_results["ATR"][-1].value if "ATR" in ta_results else (meta["point"] * 15)
                        dist_sl = atr_val * config.sl_atr_multiplier
                        sl_points = dist_sl / meta["point"]
                        
                        tick_val_usd = (meta["point"] * meta["contract_size"])
                        if meta["is_jpy"]: tick_val_usd = tick_val_usd / cur_p
                        
                        volume = max(0.01, round(risk_amount / (sl_points * tick_val_usd), 2))
                        
                        is_buy = decision.action == "BUY"
                        sl_price = round(cur_p - dist_sl if is_buy else cur_p + dist_sl, meta["digits"])
                        # USE CONFIG RR RATIO
                        tp_price = round(cur_p + (dist_sl * config.tp_rr_ratio) if is_buy else cur_p - (dist_sl * config.tp_rr_ratio), meta["digits"])
                        
                        self.open_trades.append({
                            "symbol": symbol,
                            "direction": decision.action,
                            "open_time": current_time,
                            "open_price": cur_p,
                            "sl": sl_price,
                            "tp": tp_price,
                            "volume": volume,
                            "atr": atr_val,
                            "highest_price": cur_p if is_buy else 999999,
                            "lowest_price": cur_p if not is_buy else 0
                        })

        result.trades = sorted(self.closed_trades, key=lambda x: x.open_time)
        result.calculate_metrics(self.initial_balance)
        return result, candle_data

    def _calculate_overall_unrealized(self, prices, metas) -> float:
        pnl = 0.0
        for t in self.open_trades:
            s = t["symbol"]
            if s not in prices: continue
            m = metas[s]
            diff = (prices[s] - t["open_price"]) if t["direction"] == "BUY" else (t["open_price"] - prices[s])
            tick_v = (m["point"] * m["contract_size"])
            if m["is_jpy"]: tick_v = tick_v / prices[s]
            pnl += (diff / m["point"]) * tick_v * t["volume"]
        return pnl

    def _manage_trades_for_symbol(self, symbol, time, bar, meta, trail_on, be_mult, trail_mult) -> List[BacktestTrade]:
        high, low, close = bar["high"], bar["low"], bar["close"]
        closed, remaining = [], []
        point = meta["point"]
        
        for t in [x for x in self.open_trades if x["symbol"] == symbol]:
            hit_tp, hit_sl = False, False
            is_buy = t["direction"] == "BUY"
            
            if is_buy: t["highest_price"] = max(t["highest_price"], high)
            else: t["lowest_price"] = min(t["lowest_price"], low)
            
            if is_buy:
                if high >= t["tp"]: hit_tp = True
                elif low <= t["sl"]: hit_sl = True
            else:
                if low <= t["tp"]: hit_tp = True
                elif high >= t["sl"]: hit_sl = True
            
            if not hit_tp and not hit_sl and trail_on:
                curr_profit_pts = (close - t["open_price"]) / point if is_buy else (t["open_price"] - close) / point
                atr_pts = t["atr"] / point
                if be_mult > 0 and curr_profit_pts >= (atr_pts * be_mult):
                    if is_buy and t["sl"] < t["open_price"]: t["sl"] = t["open_price"]
                    elif not is_buy and t["sl"] > t["open_price"]: t["sl"] = t["open_price"]
                
                if trail_mult > 0:
                    dist = t["atr"] * trail_mult
                    if is_buy:
                        new_sl = t["highest_price"] - dist
                        if new_sl > t["sl"]: t["sl"] = new_sl
                    else:
                        new_sl = t["lowest_price"] + dist
                        if new_sl < t["sl"]: t["sl"] = new_sl

            if hit_tp or hit_sl:
                exit_p = t["tp"] if hit_tp else t["sl"]
                diff = (exit_p - t["open_price"]) if is_buy else (t["open_price"] - exit_p)
                tick_v = (point * meta["contract_size"])
                if meta["is_jpy"]: tick_v = tick_v / t["open_price"]
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
        
        # Merge back with other symbols' trades
        self.open_trades = [t for t in self.open_trades if t["symbol"] != symbol] + remaining
        return closed

    async def run(self, symbol: str, days: int = 90) -> BacktestResult:
        """Compatibility wrapper for single symbol."""
        res, _ = await self.run_portfolio([symbol], days)
        return res

backtester = Backtester()
