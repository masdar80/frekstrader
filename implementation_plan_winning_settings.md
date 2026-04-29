# Backtest Grid Search — Detailed Execution Plan

## User Decisions

- **Starting balance:** $200
- **Pairs:** All 5 (EURUSD, GBPUSD, USDJPY, AUDUSD, USDCHF) simultaneously
- **Period:** Full 83 days available from broker
- **Correlation filter:** OFF — test without limits
- **Weight fix:** Test TECH_CONFLUENCE=1.0 when sentiment is off as a parameter

---

## Files To Create/Modify (6 files)

| # | Action | File | Purpose |
|---|---|---|---|
| 1 | MODIFY | `app/core/backtest/backtest_result.py` | Add config tracking + extra metrics |
| 2 | MODIFY | `app/core/backtest/backtester.py` | Accept config overrides instead of global settings |
| 3 | NEW | `app/core/backtest/backtest_config.py` | Dataclass holding all tunable parameters |
| 4 | NEW | `app/core/backtest/grid_search.py` | Orchestrator: generates matrix, runs all tests, ranks results |
| 5 | NEW | `run_grid_search.py` | Standalone CLI entry point |
| 6 | MODIFY | `app/core/brain/decision_engine.py` | Accept weight override for single-source mode |

---

## Step-by-Step Execution

### STEP 1: Create `backtest_config.py`

**File:** `d:\foreks\app\core\backtest\backtest_config.py`  
**Action:** CREATE new file

This dataclass holds every tunable parameter for a single backtest run:

```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class BacktestConfig:
    """All tunable parameters for a single backtest run."""
    # Identity
    name: str = "default"
    
    # Trading mode thresholds (from TRADING_MODE_PRESETS)
    confidence_threshold: float = 0.45
    min_indicators: int = 3
    
    # Risk
    max_risk_pct: float = 1.5
    max_risk_amount_usd: float = 20.0
    max_open_positions: int = 5
    allow_multiple_per_pair: bool = False
    
    # SL/TP geometry
    sl_atr_multiplier: float = 2.0       # SL distance = ATR × this
    tp_rr_ratio: float = 2.0             # TP distance = SL distance × this
    
    # Trailing stop
    trailing_stop_enabled: bool = True
    trailing_breakeven_atr_mult: float = 1.0
    trailing_atr_mult: float = 1.5
    
    # Signal weights
    tech_weight: float = 1.0             # Weight for TECH_CONFLUENCE (1.0 when sentiment off)
    
    # Portfolio
    initial_balance: float = 200.0
    use_correlation_filter: bool = False  # OFF per user request
    
    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}
```

### STEP 2: Modify `decision_engine.py`

**File:** `d:\foreks\app\core\brain\decision_engine.py`  
**Action:** MODIFY — Add `evaluate_signals_with_config()` method

Add a new method that accepts a weight override. The existing `evaluate_signals()` stays untouched for live trading.

```python
def evaluate_signals_with_config(self, symbol: str, signals: List[StandardSignal], 
                                  confidence_threshold: float, 
                                  tech_weight: float = 1.0) -> DecisionResult:
    """Backtest version: uses provided threshold and weight instead of global settings."""
    if not signals:
        return DecisionResult(symbol, "REJECT", 0.0, "No signals.", [])

    buy_score = 0.0
    sell_score = 0.0
    total_weight = 0.0
    
    for sig in signals:
        weight = tech_weight if sig.source == "TECH_CONFLUENCE" else 0.0
        total_weight += weight
        if sig.direction == "BUY":
            buy_score += (sig.confidence * weight)
        elif sig.direction == "SELL":
            sell_score += (sig.confidence * weight)
    
    if total_weight > 0:
        buy_confidence = buy_score / total_weight
        sell_confidence = sell_score / total_weight
    else:
        buy_confidence = sell_confidence = 0.0

    winner = "NEUTRAL"
    final_confidence = 0.0
    if buy_confidence > sell_confidence:
        winner = "BUY"
        final_confidence = buy_confidence
    elif sell_confidence > buy_confidence:
        winner = "SELL"
        final_confidence = sell_confidence

    if final_confidence < confidence_threshold:
        return DecisionResult(symbol, "REJECT", final_confidence,
                              f"Below threshold {confidence_threshold:.2f}", signals)

    return DecisionResult(symbol, winner, final_confidence,
                          f"APPROVED: {winner} conf={final_confidence:.2f}", signals)
```

### STEP 3: Modify `backtest_result.py`

**File:** `d:\foreks\app\core\backtest\backtest_result.py`  
**Action:** MODIFY — Add config tracking and extra metrics

Add these fields to `BacktestResult`:

```python
config_name: str = ""
config_dict: Dict[str, Any] = field(default_factory=dict)
sharpe_ratio: float = 0.0
max_consecutive_losses: int = 0
avg_win: float = 0.0
avg_loss: float = 0.0
return_pct: float = 0.0
```

In `calculate_metrics()`, add:
- Sharpe ratio from equity curve
- Max consecutive losses count
- Average win $ vs average loss $
- Return % = total_profit / initial_balance × 100
- Include these in `to_dict()` output

### STEP 4: Modify `backtester.py`

**File:** `d:\foreks\app\core\backtest\backtester.py`  
**Action:** MODIFY — Accept `BacktestConfig` override

Key changes to `run_portfolio()`:

1. **New signature:** `async def run_portfolio(self, symbols, days, config=None, candle_cache=None)`
2. **Use config instead of settings:** Replace all `settings.xxx` references with `config.xxx`
3. **Accept pre-fetched candle cache:** So we only fetch candles from broker ONCE across all 270+ runs
4. **Use `decision_engine.evaluate_signals_with_config()`** instead of `evaluate_signals()`
5. **SL/TP use config:** `sl_distance = atr × config.sl_atr_multiplier`, `tp_distance = sl_distance × config.tp_rr_ratio`
6. **No correlation filter** (config.use_correlation_filter = False)
7. **Return candle_cache** for reuse: `return result, candle_data`

The full modified replay loop logic stays the same (iterate hourly bars, check closures, check entries), but reads all parameters from the `BacktestConfig` object.

### STEP 5: Create `grid_search.py`

**File:** `d:\foreks\app\core\backtest\grid_search.py`  
**Action:** CREATE new file

This is the main orchestrator. Here's the exact logic:

```python
import itertools
import json
import time
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
        max_positions_list = [1, 3, 5, 8, 15]
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
        
        return configs  # 5×5×2×3×3 = 450 configs
    
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
            cfg = BacktestConfig(**base_config.to_dict())
            cfg.name = f"{base_config.name}__trail{trail_on}_be{be_mult}_tr{tr_mult}_sl{sl_mult}"
            cfg.trailing_stop_enabled = trail_on
            cfg.trailing_breakeven_atr_mult = be_mult
            cfg.trailing_atr_mult = tr_mult
            cfg.sl_atr_multiplier = sl_mult
            configs.append(cfg)
        
        return configs  # 2×3×3×3 = 54 per base config
    
    async def run_phase1(self) -> List[Dict[str, Any]]:
        """Run Phase 1 coarse sweep. Fetch candles ONCE, reuse for all runs."""
        configs = self.generate_phase1_configs()
        logger.info(f"=== PHASE 1: {len(configs)} configurations to test ===")
        
        candle_cache = None  # Will be populated on first run
        results = []
        
        for i, config in enumerate(configs):
            bt = Backtester()
            bt.initial_balance = config.initial_balance
            
            result, candle_cache = await bt.run_portfolio(
                self.symbols, self.days, config=config, candle_cache=candle_cache
            )
            
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
        
        top_configs = self.results[:top_n]
        phase2_results = []
        candle_cache = None
        
        for base_entry in top_configs:
            base_config = BacktestConfig(**{k: v for k, v in base_entry["config"].items() if k != "name"})
            base_config.name = base_entry["name"]
            fine_configs = self.generate_phase2_configs(base_config)
            
            logger.info(f"=== PHASE 2: Fine-tuning '{base_config.name}' ({len(fine_configs)} variants) ===")
            
            for config in fine_configs:
                bt = Backtester()
                bt.initial_balance = config.initial_balance
                result, candle_cache = await bt.run_portfolio(
                    self.symbols, self.days, config=config, candle_cache=candle_cache
                )
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
    
    def print_leaderboard(self, results: List[Dict], title: str = "LEADERBOARD", top_n: int = 20):
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
```

### STEP 6: Create `run_grid_search.py`

**File:** `d:\foreks\run_grid_search.py`  
**Action:** CREATE new file

```python
"""
ForeksTrader Grid Search — Find the optimal configuration.
Usage: python run_grid_search.py
"""
import asyncio
import json
from app.core.broker.metaapi_client import broker
from app.core.backtest.grid_search import GridSearch

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF"]
DAYS = 83

async def main():
    print("=" * 60)
    print("  ForeksTrader Grid Search Optimizer")
    print("=" * 60)
    
    # 1. Connect to broker for candle data
    print("\n[1/5] Connecting to MetaAPI broker...")
    connected = await broker.connect()
    if not connected:
        print("FATAL: Cannot connect to broker. Check .env credentials.")
        return
    print("  ✅ Connected!")
    
    # 2. Initialize grid search
    print(f"\n[2/5] Initializing grid search for {SYMBOLS}...")
    gs = GridSearch(symbols=SYMBOLS, days=DAYS)
    
    # 3. Phase 1: Coarse sweep
    print(f"\n[3/5] Running Phase 1 coarse sweep...")
    phase1_results = await gs.run_phase1()
    gs.print_leaderboard(phase1_results, "PHASE 1 — COARSE SWEEP RESULTS", top_n=15)
    gs.save_results(phase1_results, "backtest_phase1_results.json")
    
    # 4. Phase 2: Fine-tune top 3
    print(f"\n[4/5] Running Phase 2 fine-tune on top 3 winners...")
    phase2_results = await gs.run_phase2(top_n=3)
    gs.print_leaderboard(phase2_results, "PHASE 2 — FINE-TUNED RESULTS", top_n=15)
    gs.save_results(phase2_results, "backtest_phase2_results.json")
    
    # 5. Final recommendation
    if phase2_results:
        best = phase2_results[0]
        print("\n" + "=" * 60)
        print("  🏆 RECOMMENDED CONFIGURATION")
        print("=" * 60)
        print(json.dumps(best["config"], indent=2))
        print(f"\n  Expected Return: {best['return_pct']:.1f}%")
        print(f"  Win Rate: {best['win_rate']:.1f}%")
        print(f"  Max Drawdown: {best['max_drawdown']:.1f}%")
        print(f"  Total Trades: {best['total_trades']}")
    
    # Cleanup
    await broker.disconnect()
    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Critical Implementation Details

### Candle Cache Sharing

The **most important optimization**: candle data is fetched from MetaAPI only ONCE on the first backtest run. The `run_portfolio()` method returns the fetched candle data, and all subsequent runs reuse it. Without this, 450 runs × 5 symbols × 4 timeframes = 9,000 API calls (would take hours and hit rate limits).

**In `backtester.py`, the modified signature:**
```python
async def run_portfolio(self, symbols, days, config=None, candle_cache=None):
    # If candle_cache is provided, skip fetching
    if candle_cache:
        candle_data = candle_cache
    else:
        candle_data = {}
        for symbol in symbols:
            # ... fetch from broker (existing code) ...
    
    # ... run replay loop using config params ...
    
    return result, candle_data  # Return cache for reuse
```

### Parameter Override in Replay Loop

Inside `run_portfolio()`, replace every `settings.xxx` with `config.xxx`:

| Original (settings) | Replacement (config) |
|---|---|
| `settings.max_open_positions` | `config.max_open_positions` |
| `settings.allow_multiple_per_pair` | `config.allow_multiple_per_pair` |
| `settings.trailing_stop_enabled` | `config.trailing_stop_enabled` |
| `settings.trailing_breakeven_atr_mult` | `config.trailing_breakeven_atr_mult` |
| `settings.trailing_atr_mult` | `config.trailing_atr_mult` |
| `settings.effective_max_risk_pct` | `config.max_risk_pct` |
| `settings.max_risk_amount_usd` | `config.max_risk_amount_usd` |
| `settings.confidence_threshold` | `config.confidence_threshold` |
| `atr_val * 2.0` (SL) | `atr_val * config.sl_atr_multiplier` |
| `dist_sl * 2` (TP) | `dist_sl * config.tp_rr_ratio` |

### Decision Engine Call

Replace:
```python
decision = decision_engine.evaluate_signals(symbol, [signal])
```
With:
```python
decision = decision_engine.evaluate_signals_with_config(
    symbol, [signal], 
    confidence_threshold=config.confidence_threshold,
    tech_weight=config.tech_weight
)
```

### No Correlation Filter

The existing backtester does NOT have the correlation filter from `risk_manager.py`. The only filters in the backtest are:
- Max open positions check
- Allow multiple per pair check

Both are already parameterized. No additional changes needed.

---

## Verification Plan

1. **Run a single test first** with default settings to verify candle fetching works
2. **Check Phase 1 output** has exactly 450 rows (5×5×2×3×3)
3. **Check Phase 2 output** has 162 rows (3 winners × 54 variants each)
4. **Validate that top results show positive profit** — if ALL 450 configs lose money, the strategy itself needs rethinking (not just parameters)

## Expected Runtime

- Candle fetch: ~2-3 minutes (one-time)
- Phase 1 (450 runs): ~10-20 minutes (pure computation, no API calls)
- Phase 2 (162 runs): ~5-10 minutes
- **Total: ~20-30 minutes**
