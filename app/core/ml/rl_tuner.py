import numpy as np
from typing import Dict, Any, List
from app.utils.logger import logger
from app.backtest.backtester import Backtester

class ParameterTuner:
    """
    Uses a simple Evolutionary Algorithm to find the optimal 
    ATR multipliers for SL, TP, and Trailing Stops over historical data.
    Runs completely on CPU.
    """
    def __init__(self, symbol: str, start_dt: str, end_dt: str, pop_size=10, generations=5):
        self.symbol = symbol
        self.start_dt = start_dt
        self.end_dt = end_dt
        self.pop_size = pop_size
        self.generations = generations
        
    def _evaluate(self, params: Dict[str, float]) -> float:
        from app.config import settings
        orig_sl = settings.risk_atr_mult_sl
        orig_tp = settings.risk_atr_mult_tp
        orig_trail = settings.trailing_atr_mult
        
        settings.risk_atr_mult_sl = params["sl"]
        settings.risk_atr_mult_tp = params["tp"]
        settings.trailing_atr_mult = params["trail"]
        
        bt = Backtester(self.symbol, self.start_dt, self.end_dt)
        try:
            res = bt.run()
            score = res.get("total_pips", -9999)
        except Exception as e:
            score = -9999
            
        settings.risk_atr_mult_sl = orig_sl
        settings.risk_atr_mult_tp = orig_tp
        settings.trailing_atr_mult = orig_trail
        
        return score
        
    def optimize(self) -> Dict[str, float]:
        logger.info(f"Starting parameter optimization over {self.generations} generations...")
        
        population = [
            {
                "sl": np.random.uniform(1.0, 3.0),
                "tp": np.random.uniform(1.0, 5.0),
                "trail": np.random.uniform(0.5, 2.5)
            } for _ in range(self.pop_size)
        ]
        
        best_params = None
        best_score = -float('inf')
        
        for gen in range(self.generations):
            scores = []
            for ind in population:
                score = self._evaluate(ind)
                scores.append((score, ind))
                
                if score > best_score:
                    best_score = score
                    best_params = ind.copy()
                    
            scores.sort(key=lambda x: x[0], reverse=True)
            logger.info(f"Gen {gen+1} Best Score: {scores[0][0]:.2f} pips")
            
            survivors = [x[1] for x in scores[:self.pop_size//2]]
            
            next_gen = survivors.copy()
            while len(next_gen) < self.pop_size:
                p1 = np.random.choice(survivors)
                p2 = np.random.choice(survivors)
                child = {
                    "sl": (p1["sl"] + p2["sl"]) / 2 + np.random.normal(0, 0.2),
                    "tp": (p1["tp"] + p2["tp"]) / 2 + np.random.normal(0, 0.2),
                    "trail": (p1["trail"] + p2["trail"]) / 2 + np.random.normal(0, 0.2)
                }
                child["sl"] = max(0.5, child["sl"])
                child["tp"] = max(0.5, child["tp"])
                child["trail"] = max(0.2, child["trail"])
                next_gen.append(child)
                
            population = next_gen
            
        logger.info(f"Optimization Complete. Best Pips: {best_score:.2f}")
        logger.info(f"Optimal Params: {best_params}")
        return best_params
