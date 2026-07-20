import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backtest.backtester import Backtester
from app.config import settings
from app.utils.logger import logger
import logging

# Disable logger spam for the optimizer
logger.setLevel(logging.WARNING)

def run_scenario(name, sl, tp, trailing, trail_start, trail_dist):
    # Override settings
    settings.risk_atr_mult_sl = sl
    settings.risk_atr_mult_tp = tp
    settings.trailing_stop_enabled = trailing
    settings.trailing_breakeven_atr_mult = trail_start
    settings.trailing_atr_mult = trail_dist
    
    # 6-month fast test
    bt = Backtester("EURUSD", "2026-01-01", "2026-06-28")
    res = bt.run()
    
    print(f"\n--- {name} ---")
    print(f"SL={sl} ATR, TP={tp} ATR, Trailing={trailing} (Start:{trail_start}, Dist:{trail_dist})")
    print(f"Win Rate:   {res['win_rate']*100:.2f}% ({res['wins']}W / {res['losses']}L)")
    print(f"Total Pips: {res['total_pips']:.2f}")

print("Evaluating strategies based on ML insights...")
# Scenario 1: Symmetrical Scalp (1.5:1.5)
run_scenario("Short-Term Symmetrical", 1.5, 1.5, False, 1.0, 1.0)

# Scenario 2: Tight Trail (Cut losses short, trail profits)
run_scenario("Tight Trailing", 1.0, 2.5, True, 1.0, 1.0)

# Scenario 3: Aggressive Scalp (1.0:1.5)
run_scenario("Aggressive Scalp", 1.0, 1.5, False, 1.0, 1.0)

