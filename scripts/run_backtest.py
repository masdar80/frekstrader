import sys
import os

# Add parent directory to path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.backtest.backtester import Backtester
    from app.utils.logger import logger
except Exception as e:
    import traceback
    print("\n💥 BACKTEST IMPORT CRASHED:")
    traceback.print_exc()
    sys.exit(1)

def main():
    symbol = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
    start_dt = "2026-01-01"
    end_dt = "2026-06-28"
    
    logger.info(f"Running backtest for {symbol} from {start_dt} to {end_dt}...")
    
    print("[1/4] Initializing Backtester...", flush=True)
    bt = Backtester(symbol, start_dt, end_dt)
    
    print("[2/4] Backtester initialized successfully. Starting simulation...", flush=True)
    results = bt.run()
    
    print("[3/4] Simulation finished. Generating report...", flush=True)
    print("\n" + "="*40)
    print(f"      BACKTEST RESULTS: {symbol}")
    print("="*40)
    print(f"Total Trades: {results.get('total_trades')}")
    print(f"Wins:         {results.get('wins')}")
    print(f"Losses:       {results.get('losses')}")
    print(f"Win Rate:     {results.get('win_rate') * 100:.2f}%")
    print(f"Total Pips:   {results.get('total_pips')} pips")
    print("="*40, flush=True)
    
    print("\n--- FIRST 10 TRADES ---")
    for t in results.get("trades", [])[:10]:
        print(f"{t.direction} at {t.entry_price:.5f} | Close: {t.close_price:.5f} | Reason: {t.close_reason} | Pips: {t.profit_pips:.2f} | ATR: {t.atr:.5f}")

if __name__ == "__main__":
    try:
        main()
    except BaseException as e:
        import traceback
        print("\n💥 BACKTEST CRASHED (BaseException):", flush=True)
        traceback.print_exc()
        sys.exit(1)
