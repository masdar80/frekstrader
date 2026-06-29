import numpy as np
from typing import List, Dict, Any
from app.utils.logger import logger

class MonteCarloSimulator:
    """
    Runs Monte Carlo permutations on backtest results to analyze
    drawdown probability and risk of ruin.
    """
    def __init__(self, initial_balance: float = 1000.0, risk_per_trade_pct: float = 0.02):
        self.initial_balance = initial_balance
        self.risk_per_trade_pct = risk_per_trade_pct
        
    def simulate(self, trade_pips: List[float], iterations: int = 1000) -> Dict[str, Any]:
        logger.info(f"Running Monte Carlo ({iterations} iterations) on {len(trade_pips)} trades...")
        if not trade_pips:
            return {}
            
        trade_array = np.array(trade_pips)
        
        final_balances = []
        max_drawdowns = []
        ruins = 0
        
        losses = [p for p in trade_pips if p < 0]
        avg_loss_pips = abs(np.mean(losses)) if losses else 30.0
        
        for _ in range(iterations):
            # Sample with replacement
            shuffled = np.random.choice(trade_array, size=len(trade_array), replace=True)
            
            balance = self.initial_balance
            peak = balance
            max_dd = 0.0
            
            for pips in shuffled:
                risk_amount = balance * self.risk_per_trade_pct
                pip_value = risk_amount / max(1.0, avg_loss_pips)
                trade_pnl = pips * pip_value
                
                balance += trade_pnl
                
                if balance > peak:
                    peak = balance
                
                dd = (peak - balance) / peak
                if dd > max_dd:
                    max_dd = dd
                    
                if balance <= 0:
                    balance = 0
                    ruins += 1
                    break
                    
            final_balances.append(balance)
            max_drawdowns.append(max_dd)
            
        avg_final = np.mean(final_balances)
        avg_dd = np.mean(max_drawdowns)
        worst_dd = np.max(max_drawdowns)
        risk_of_ruin = ruins / iterations
        
        logger.info(f"MC Avg Final Balance: ${avg_final:.2f}")
        logger.info(f"MC Avg Max Drawdown: {avg_dd*100:.1f}%")
        logger.info(f"MC Risk of Ruin: {risk_of_ruin*100:.1f}%")
        
        return {
            "avg_final_balance": avg_final,
            "avg_max_drawdown": avg_dd,
            "worst_drawdown": worst_dd,
            "risk_of_ruin": risk_of_ruin
        }

monte_carlo = MonteCarloSimulator()
