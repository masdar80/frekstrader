"""
ForeksTrader Grid Search — Find the optimal configuration.
Usage: python run_grid_search.py
"""
import asyncio
import json
import os
import sys
import logging

# Ensure app directory is in path
sys.path.append(os.getcwd())

from app.core.broker.metaapi_client import broker
from app.core.backtest.grid_search import GridSearch
from app.utils.logger import logger

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF"]
DAYS = 83

async def main():
    print("\n" + "=" * 60)
    print("  ForeksTrader Grid Search Optimizer")
    print("=" * 60)
    
    # Silence spammy logs for the sweep
    logger.setLevel(logging.ERROR)
    
    # 1. Connect to broker for candle data
    print("\n[1/5] Connecting to MetaAPI broker...")
    try:
        connected = await broker.connect()
        if not connected:
            print("FATAL: Cannot connect to broker. Check .env credentials.")
            return
        print("  [OK] Connected!")
    except Exception as e:
        print(f"FATAL: Broker connection error: {e}")
        return
    
    # 2. Initialize grid search
    print(f"\n[2/5] Initializing grid search for {SYMBOLS} over {DAYS} days...")
    gs = GridSearch(symbols=SYMBOLS, days=DAYS)
    
    # 3. Phase 1: Coarse sweep
    print(f"\n[3/5] Running Phase 1 coarse sweep (This will take a few minutes)...")
    try:
        phase1_results = await gs.run_phase1()
        gs.print_leaderboard(phase1_results, "PHASE 1 - COARSE SWEEP RESULTS", top_n=15)
        gs.save_results(phase1_results, "backtest_phase1_results.json")
    except Exception as e:
        print(f"ERROR in Phase 1: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 4. Phase 2: Fine-tune top 3
    if phase1_results:
        print(f"\n[4/5] Running Phase 2 fine-tune on top 3 winners...")
        try:
            phase2_results = await gs.run_phase2(top_n=3)
            gs.print_leaderboard(phase2_results, "PHASE 2 - FINE-TUNED RESULTS", top_n=15)
            gs.save_results(phase2_results, "backtest_phase2_results.json")
        except Exception as e:
            print(f"ERROR in Phase 2: {e}")
            return
    else:
        print("\n[4/5] Skipping Phase 2: No results from Phase 1.")
        phase2_results = []
    
    # 5. Final recommendation
    final_winner = phase2_results[0] if phase2_results else (phase1_results[0] if phase1_results else None)
    
    if final_winner:
        print("\n" + "=" * 60)
        print("  RECOMMENDED CONFIGURATION")
        print("=" * 60)
        # Pretty print the config
        print(json.dumps(final_winner["config"], indent=4))
        print(f"\n  Expected Return (83 days): {final_winner['return_pct']:.1f}%")
        print(f"  Win Rate: {final_winner['win_rate']:.1f}%")
        print(f"  Profit Factor: {final_winner['profit_factor']:.2f}")
        print(f"  Max Drawdown: {final_winner['max_drawdown']:.1f}%")
        print(f"  Total Trades: {final_winner['total_trades']}")
        print("=" * 60)
    else:
        print("\n[!] No profitable configurations found.")
    
    # Cleanup
    await broker.disconnect()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
