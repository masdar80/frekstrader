import sys
import os
import asyncio
import pandas as pd
from datetime import datetime
from sqlalchemy import delete

# Add parent directory to path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import async_session
from app.db.models import FeatureSnapshot
from app.data.candle_store import candle_store
from app.core.analysis.technical import technical_analyzer, IndicatorResult
from app.core.analysis.regime import regime_detector
from app.core.analysis.signals import StandardSignal
from app.core.brain.decision_engine import decision_engine
from app.config import settings
from app.utils.logger import logger

def get_trade_outcome(df_15m, start_idx, action, entry_price, sl, tp, pip_size):
    """Scan forward in M15 candles to determine if SL or TP was hit first."""
    for i in range(start_idx, len(df_15m)):
        row = df_15m.iloc[i]
        high = row["high"]
        low = row["low"]
        
        if action == "BUY":
            if low <= sl:
                return "LOSS", round((sl - entry_price) / pip_size, 2)
            elif high >= tp:
                return "WIN", round((tp - entry_price) / pip_size, 2)
        else: # SELL
            if high >= sl:
                return "LOSS", round((entry_price - sl) / pip_size, 2)
            elif low <= tp:
                return "WIN", round((entry_price - tp) / pip_size, 2)
                
    # Default to last candle close if never hit before data ends
    final_close = df_15m.iloc[-1]["close"]
    profit_pips = (final_close - entry_price) / pip_size if action == "BUY" else (entry_price - final_close) / pip_size
    return ("WIN" if profit_pips > 0 else "LOSS"), round(profit_pips, 2)

async def generate():
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF"]
    start_dt = "2024-01-02"
    end_dt = "2026-06-28"
    
    print("--- ML Dataset Generation from Parquet ---")
    
    snapshots = []
    
    # 1. Clear database first
    print("Clearing 'feature_snapshots' table...", flush=True)
    async with async_session() as db:
        await db.execute(delete(FeatureSnapshot))
        await db.commit()

    for symbol in symbols:
        print(f"\nProcessing symbol: {symbol}", flush=True)
        pip_size = 0.01 if "JPY" in symbol else 0.0001
        spread_val = 1.5 * pip_size
        
        # Load and precompute
        df_15m = candle_store.get_slice(symbol, "15m", start_dt, end_dt)
        df_1h = candle_store.get_slice(symbol, "1h", start_dt, end_dt)
        df_4h = candle_store.get_slice(symbol, "4h", start_dt, end_dt)
        df_1d = candle_store.get_slice(symbol, "1d", start_dt, end_dt)
        
        df_15m = technical_analyzer.precompute(df_15m)
        df_1h = technical_analyzer.precompute(df_1h)
        df_4h = technical_analyzer.precompute(df_4h)
        df_1d = technical_analyzer.precompute(df_1d)
        
        df_by_tf = {
            "15m": df_15m,
            "1h": df_1h,
            "4h": df_4h,
            "1d": df_1d
        }
        
        total_rows = len(df_15m)
        for idx in range(100, total_rows): # start at 100 to ensure indicators have warmed up
            current_time = df_15m.index[idx]
            row_15m = df_15m.iloc[idx]
            close = row_15m["close"]
            
            # Calculate technical signals
            ta_raw_results = technical_analyzer.analyze_row(df_by_tf, current_time)
            ta_confluence = technical_analyzer.get_confluence_score(ta_raw_results)
            regime_info = regime_detector.detect(symbol, ta_raw_results)
            
            tech_sig = StandardSignal(
                symbol=symbol,
                source="TECH_CONFLUENCE",
                direction=ta_confluence["direction"],
                strength=ta_confluence["confidence"],
                confidence=ta_confluence["confidence"],
                reasoning=f"Confluence: buy_votes={ta_confluence['buy_votes']}, sell_votes={ta_confluence['sell_votes']}",
                metadata={"breakdown": ta_confluence["breakdown"]}
            )
            
            decision = decision_engine.evaluate_signals(symbol, [tech_sig], regime_info)
            
            indicators_json = {}
            for tf, indicator_list in ta_raw_results.items():
                indicators_json[tf] = {}
                for res in indicator_list:
                    indicators_json[tf][res.name] = res.value
                    
            hour = current_time.hour
            day = current_time.dayofweek
            
            atr_1h = 0.0010
            if "ATR" in ta_raw_results:
                for res in ta_raw_results["ATR"]:
                    if res.timeframe == "1h":
                        atr_1h = res.details.get("atr", 0.0010)
                        break
            
            atr_4h = 0.0020
            if "ATR" in ta_raw_results:
                for res in ta_raw_results["ATR"]:
                    if res.timeframe == "4h":
                        atr_4h = res.details.get("atr", 0.0020)
                        break
            
            outcome = None
            profit_pips = None
            
            if decision.action in ["BUY", "SELL"]:
                entry_price = close + spread_val if decision.action == "BUY" else close - spread_val
                sl_dist = atr_1h * settings.risk_atr_mult_sl
                tp_dist = atr_1h * settings.risk_atr_mult_tp
                
                sl = entry_price - sl_dist if decision.action == "BUY" else entry_price + sl_dist
                tp = entry_price + tp_dist if decision.action == "BUY" else entry_price - tp_dist
                
                outcome, profit_pips = get_trade_outcome(df_15m, idx + 1, decision.action, entry_price, sl, tp, pip_size)
            elif decision.action == "REJECT":
                outcome = "REJECT"
                profit_pips = 0.0
                
            if outcome:
                snapshot = FeatureSnapshot(
                    timestamp=current_time.to_pydatetime(),
                    symbol=symbol,
                    indicators_json=indicators_json,
                    hour_of_day=hour,
                    day_of_week=day,
                    spread_pips=1.5,
                    atr_1h=atr_1h,
                    atr_4h=atr_4h,
                    market_regime=regime_info.get("regime", "UNKNOWN"),
                    outcome=outcome,
                    profit_pips=profit_pips
                )
                snapshots.append(snapshot)
                
            if idx % 15000 == 0:
                print(f"  [{symbol}] Processed {idx}/{total_rows} rows... Total snapshots: {len(snapshots)}", flush=True)
                
    print(f"\n3. Simulating finished. Generated {len(snapshots)} total snapshots. Writing to database...", flush=True)
    
    # Save to SQLite
    async with async_session() as db:
        # Add all snapshots in a single transaction
        db.add_all(snapshots)
        await db.commit()
        
    print(f"🎉 Success! Wrote {len(snapshots)} feature snapshots to 'feature_snapshots' table.", flush=True)

if __name__ == "__main__":
    asyncio.run(generate())
