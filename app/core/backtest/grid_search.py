import itertools
import json
import time
import asyncio
from typing import List, Dict, Any
from app.core.backtest.backtest_config import BacktestConfig
from app.core.backtest.backtester import Backtester
from app.utils.logger import logger

# Mode presets mapping
MODE_PRESETS = {
    "ultra_conservative": {"confidence_threshold": 0.75, "max_risk_pct": 0.5, "min_indicators": 5},
    "conservative":       {"confidence_threshold": 0.60, "max_risk_pct": 1.0, "min_indicators": 4},
    "balanced":           {"confidence_threshold": 0.45, "max_risk_pct": 1.5, "min_indicators": 3},
    "aggressive":         {"confidence_threshold": 0.35, "max_risk_pct": 2.5, "min_indicators": 2},
    "ultra_aggressive":   {"confidence_threshold": 0.25, "max_risk_pct": 4.0, "min_indicators": 1},
}

class GridSearch:
    def __init__(self, symbols: List[str], days: int = 83):
        self.symbols = symbols
        self.days = days
        self.results: List[Dict[str, Any]] = []
    
    def generate_phase1_configs(self) -> List[BacktestConfig]:
        """Phase 1: Coarse sweep — 5 most impactful parameters."""
        configs = []
        
        modes = ["ultra_conservative", "conservative", "balanced", "aggressive", "ultra_aggressive"]
        max_positions_list = [1, 5, 15] # Reduced from [1,3,5,8,15] to speed up initial sweep
        multi_pair_list = [True, False]
        risk_amounts = [10.0, 20.0, 50.0]
        rr_ratios = [1.5, 2.0, 3.0]
        
        for mode, max_pos, multi, risk_amt, rr in itertools.product(
            modes, max_positions_list, multi_pair_list, risk_amounts, rr_ratios
        ):
            preset = MODE_PRESETS[mode]
            name = f"{mode}_pos{max_pos}_multi{multi}_risk{risk_amt}_rr{rr}"
            configs.append(BacktestConfig(
                name=name,
                confidence_threshold=preset["confidence_threshold"],
                max_risk_pct=preset["max_risk_pct"],
                min_indicators=preset["min_indicators"],
                max_open_positions=max_pos,
                allow_multiple_per_pair=multi,
                max_risk_amount_usd=risk_amt,
                tp_rr_ratio=rr,
                sl_atr_multiplier=2.0,
                trailing_stop_enabled=True,
                trailing_breakeven_atr_mult=1.0,
                trailing_atr_mult=1.5,
                tech_weight=1.0,
                initial_balance=200.0,
                use_correlation_filter=False,
            ))
        
        return configs  # 5x3x2x3x3 = 270 configs
    
    def generate_phase2_configs(self, base_config: BacktestConfig) -> List[BacktestConfig]:
        """Phase 2: Fine-tune trailing/ATR on a winning config."""
        configs = []
        
        trailing_enabled = [True, False]
        be_atr_mults = [0.5, 1.0, 1.5]
        trail_atr_mults = [1.0, 1.5, 2.5]
        sl_atr_mults = [1.5, 2.0, 3.0]
        
        for trail_on, be_mult, tr_mult, sl_mult in itertools.product(
            trailing_enabled, be_atr_mults, trail_atr_mults, sl_atr_mults
        ):
            # Create dict excluding name and pass as kwargs
            cfg_dict = base_config.to_dict()
            cfg_name_base = cfg_dict.pop("name")
            
            cfg = BacktestConfig(
                name=f"{cfg_name_base}__trail{trail_on}_be{be_mult}_tr{tr_mult}_sl{sl_mult}",
                **cfg_dict
            )
            cfg.trailing_stop_enabled = trail_on
            cfg.trailing_breakeven_atr_mult = be_mult
            cfg.trailing_atr_mult = tr_mult
            cfg.sl_atr_multiplier = sl_mult
            configs.append(cfg)
        
        return configs  # 2x3x3x3 = 54 per base config
    
    async def run_phase1(self) -> List[Dict[str, Any]]:
        """Run Phase 1 coarse sweep. Fetch candles ONCE, reuse for all runs."""
        configs = self.generate_phase1_configs()
        logger.info(f"=== PHASE 1: {len(configs)} configurations to test ===")
        
        candle_cache = None  # Will be populated on first run
        results = []
        
        for i, config in enumerate(configs):
            # Heartbeat for background monitoring
            print(f"  [PHASE 1] Config {i+1}/{len(configs)}: {config.name}", flush=True)
            
            bt = Backtester()
            bt.initial_balance = config.initial_balance
            
            result, candle_cache = await bt.run_portfolio(
                self.symbols, self.days, config=config, candle_cache=candle_cache
            )
            
            if not result:
                continue
                
            entry = {
                "rank": 0,
                "name": config.name,
                "config": config.to_dict(),
                "total_trades": result.total_trades,
                "win_rate": result.win_rate,
                "total_profit": result.total_profit,
                "return_pct": result.return_pct,
                "max_drawdown": result.max_drawdown,
                "profit_factor": result.profit_factor,
                "sharpe_ratio": result.sharpe_ratio,
            }
            results.append(entry)
            
            if (i + 1) % 25 == 0:
                logger.info(f"  Progress: {i+1}/{len(configs)} completed")
        
        # Sort by total_profit descending
        results.sort(key=lambda x: x["total_profit"], reverse=True)
        for i, r in enumerate(results):
            r["rank"] = i + 1
        
        self.results = results
        return results
    
    async def run_phase2(self, top_n: int = 3) -> List[Dict[str, Any]]:
        """Take top N from Phase 1, fine-tune trailing/ATR params."""
        if not self.results:
            return []
        
        top_entries = self.results[:top_n]
        phase2_results = []
        
        # We need the candle cache from somewhere - we'll just fetch once in run_phase1 and reuse
        # In a real scenario we'd pass it in, but for this script we'll just fetch again if needed
        # though run_phase1 already populated it. 
        # Actually, let's fetch once at the very start of run_grid_search and pass it to both.
        
        # For simplicity within this class, we'll re-fetch if run_phase2 is called alone.
        candle_cache = None 
        
        for base_entry in top_entries:
            # Reconstruct config from dict
            cfg_data = dict(base_entry["config"])
            cfg_name = cfg_data.pop("name")
            base_config = BacktestConfig(name=cfg_name, **cfg_data)
            
            fine_configs = self.generate_phase2_configs(base_config)
            
            logger.info(f"=== PHASE 2: Fine-tuning '{base_config.name}' ({len(fine_configs)} variants) ===")
            
            for i, config in enumerate(fine_configs):
                print(f"  [PHASE 2] {base_config.name} variant {i+1}/{len(fine_configs)}", flush=True)
                bt = Backtester()
                bt.initial_balance = config.initial_balance
                result, candle_cache = await bt.run_portfolio(
                    self.symbols, self.days, config=config, candle_cache=candle_cache
                )
                
                if not result: continue
                
                phase2_results.append({
                    "name": config.name,
                    "config": config.to_dict(),
                    "total_trades": result.total_trades,
                    "win_rate": result.win_rate,
                    "total_profit": result.total_profit,
                    "return_pct": result.return_pct,
                    "max_drawdown": result.max_drawdown,
                    "profit_factor": result.profit_factor,
                    "sharpe_ratio": result.sharpe_ratio,
                })
        
        phase2_results.sort(key=lambda x: x["total_profit"], reverse=True)
        for i, r in enumerate(phase2_results):
            r["rank"] = i + 1
        
        return phase2_results
    
    def print_leaderboard(self, results: List[Dict], title: str = "LEADERBOARD", top_n: int = 15):
        """Pretty-print top results."""
        print(f"\n{'='*100}")
        print(f"  {title}")
        print(f"{'='*100}")
        print(f"{'#':>3} | {'Profit':>10} | {'Return%':>8} | {'WinRate':>7} | {'Trades':>6} | {'MaxDD':>7} | {'PF':>6} | {'Sharpe':>7} | Config")
        print(f"{'-'*100}")
        
        for r in results[:top_n]:
            print(
                f"{r['rank']:>3} | "
                f"${r['total_profit']:>9.2f} | "
                f"{r['return_pct']:>7.1f}% | "
                f"{r['win_rate']:>6.1f}% | "
                f"{r['total_trades']:>6} | "
                f"{r['max_drawdown']:>6.1f}% | "
                f"{r['profit_factor']:>5.2f} | "
                f"{r['sharpe_ratio']:>6.2f} | "
                f"{r['name'][:50]}"
            )
        
        print(f"{'='*100}")

    
    def save_results(self, results: List[Dict], filename: str = "backtest_results.json"):
        """Save full results to JSON."""
        with open(filename, "w") as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Results saved to {filename}")
