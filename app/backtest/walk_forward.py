import pandas as pd
from typing import List, Dict, Any
from app.backtest.backtester import Backtester
from app.backtest.monte_carlo import monte_carlo
from app.utils.logger import logger

class WalkForwardEngine:
    """
    Performs Walk-Forward Validation.
    Moves a testing window forward in steps to evaluate robustness.
    """
    def __init__(self, symbol: str, start_dt: str, end_dt: str, window_days: int = 30, step_days: int = 15):
        self.symbol = symbol
        self.start_dt = pd.to_datetime(start_dt)
        self.end_dt = pd.to_datetime(end_dt)
        self.window_days = window_days
        self.step_days = step_days
        
    def run(self) -> Dict[str, Any]:
        logger.info(f"Starting Walk-Forward Analysis for {self.symbol}")
        
        current_start = self.start_dt
        results = []
        
        total_pips = 0
        total_trades = 0
        total_wins = 0
        all_trade_pips = []
        
        while current_start + pd.Timedelta(days=self.window_days) <= self.end_dt:
            window_end = current_start + pd.Timedelta(days=self.window_days)
            
            logger.info(f"Running Window: {current_start.date()} -> {window_end.date()}")
            
            bt = Backtester(self.symbol, str(current_start), str(window_end))
            try:
                res = bt.run()
                res["window"] = f"{current_start.date()} to {window_end.date()}"
                results.append(res)
                
                total_pips += res["total_pips"]
                total_trades += res["total_trades"]
                total_wins += res.get("wins", 0)
                
                # Extract individual trade pips if we modify Backtester to return them.
                # Since Backtester currently returns aggregated metrics, we should modify Backtester to return trade_pips.
                if "trade_pips" in res:
                    all_trade_pips.extend(res["trade_pips"])
                
                logger.info(f"Window Pips: {res['total_pips']}, Trades: {res['total_trades']}, Win Rate: {res.get('win_rate', 0)*100:.1f}%")
            except Exception as e:
                logger.error(f"Window failed: {e}")
                
            current_start += pd.Timedelta(days=self.step_days)
            
        win_rate = total_wins / total_trades if total_trades > 0 else 0
        
        logger.info("--- Walk-Forward Complete ---")
        logger.info(f"Total OOS Pips: {total_pips:.2f}")
        logger.info(f"Total OOS Trades: {total_trades}")
        logger.info(f"Overall Win Rate: {win_rate*100:.2f}%")
        
        mc_results = monte_carlo.simulate(all_trade_pips)
        
        return {
            "total_pips": total_pips,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "monte_carlo": mc_results,
            "windows": results
        }
