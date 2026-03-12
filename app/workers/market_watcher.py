"""
Market Watcher Background Worker.
Orchestrates the entire trading pipeline for all configured currency pairs.
"""
import asyncio
from typing import List, Dict, Any

from app.config import settings
from app.utils.logger import logger
from app.core.broker.metaapi_client import broker
from app.core.analysis.technical import technical_analyzer
from app.core.analysis.sentiment import sentiment_engine
from app.core.analysis.signals import normalize_technical_signals, normalize_sentiment_signals
from app.core.brain.decision_engine import decision_engine
from app.core.risk.manager import risk_manager
from app.core.risk.position_sizer import position_sizer

from app.db.database import async_session
from app.db import crud


class MarketWatcher:
    """Runs continuously, driving the trading bot logic."""
    
    def __init__(self):
        self.is_running = False
        self.sleep_interval = 60 * 5  # Run every 5 minutes by default
        
    async def start(self):
        self.is_running = True
        logger.info("🚀 Market Watcher starting...")
        
        while self.is_running:
            try:
                if not broker.is_connected:
                    logger.warning("Broker not connected, attempting to connect...")
                    success = await broker.connect()
                    if not success:
                        await asyncio.sleep(30)
                        continue
                        
                await self._run_cycle()
                
            except Exception as e:
                logger.error(f"Error in Market Watcher main loop: {e}")
                
            # Sleep until next cycle
            await asyncio.sleep(self.sleep_interval)
            
    async def stop(self):
        self.is_running = False
        logger.info("🛑 Market Watcher stopped.")

    async def _run_cycle(self):
        """One complete execution cycle for all pairs."""
        logger.info(f"--- 🔄 Starting analysis cycle for {len(settings.pairs_list)} pairs ---")
        
        # 1. Fetch current account state
        account_info = await broker.get_account_info()
        open_positions = await broker.get_positions()
        
        async with async_session() as db:
            daily_pnl = await crud.get_daily_pnl(db)
            weekly_pnl = await crud.get_weekly_pnl(db)
            
            # Save account snapshot
            await crud.create_snapshot(
                db,
                balance=account_info.get("balance", 0),
                equity=account_info.get("equity", 0),
                margin=account_info.get("margin", 0),
                free_margin=account_info.get("free_margin", 0),
                open_positions=len(open_positions),
                daily_pnl=daily_pnl
            )
            
            peak_equity = account_info.get("equity", 0)  # Simplified for this example
            
            # 2. Iterate through pairs
            for symbol in settings.pairs_list:
                try:
                    await self._analyze_and_trade_symbol(
                        symbol, db, account_info, open_positions, daily_pnl, weekly_pnl, peak_equity
                    )
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
                
                # Small delay between pairs to avoid rate limits
                await asyncio.sleep(2)
                
            # Commit all decisions, snapshots, and trades for this cycle
            await db.commit()
                
        logger.info("--- ✅ Analysis cycle complete ---")

    async def _analyze_and_trade_symbol(
        self, symbol: str, db, account_info, open_positions, daily_pnl, weekly_pnl, peak_equity
    ):
        """The core pipeline for a single currency pair."""
        logger.info(f"🔎 Analyzing {symbol}...")
        
        # 1. Fetch Market Data (Multiple Timeframes)
        candles_by_tf = {}
        for tf in technical_analyzer.TIMEFRAMES:
            candles_by_tf[tf] = await broker.get_candles(symbol, timeframe=tf, count=100)
            
        current_price_data = await broker.get_price(symbol)
        if not current_price_data:
            logger.warning(f"Could not fetch current price for {symbol}")
            return
            
        current_price = current_price_data["ask"] # generic
        
        symbol_info = await broker.get_symbol_info(symbol)
            
        # 2. Technical Analysis
        ta_raw_results = technical_analyzer.analyze(candles_by_tf)
        ta_confluence = technical_analyzer.get_confluence_score(ta_raw_results)
        
        # 3. Sentiment Analysis
        sentiment_result = await sentiment_engine.get_sentiment(symbol)
        
        # Normalize Signals
        signals = [
            normalize_technical_signals(symbol, ta_confluence),
            normalize_sentiment_signals(symbol, sentiment_result)
        ]
        
        # Save signals to DB
        for sig in signals:
            await crud.create_signal(
                db,
                symbol=sig.symbol,
                source=sig.source,
                direction=sig.direction,
                strength=sig.strength,
                confidence=sig.confidence,
                reasoning=sig.reasoning[:1000],
                data_json=sig.metadata
            )
            
        # 4. Skeptical Brain Engine
        decision = decision_engine.evaluate_signals(symbol, signals)
        
        # 5. Risk Management & Execution
        trade_executed = False
        trade_id = None
        
        if decision.action in ["BUY", "SELL"]:
            # Check Risk
            risk_check = risk_manager.check_trade_allowed(
                symbol, account_info, open_positions, daily_pnl, weekly_pnl, peak_equity
            )
            
            if risk_check["allowed"]:
                # Get ATR for Stop Loss calculation (fallback to 15 pips if ATR fails)
                atr_val = 0.0015
                if "ATR" in ta_raw_results and ta_raw_results["ATR"]:
                    atr_val = ta_raw_results["ATR"][-1].value
                    
                # Calculate Size
                size_data = position_sizer.calculate(
                    symbol, decision.action, current_price, account_info["equity"],
                    atr_val, symbol_info, decision.confidence
                )
                
                if size_data["allowed"]:
                    # EXECUTE TRADE
                    logger.critical(f"🚀 EXECUTING {decision.action} onto {symbol} | Vol: {size_data['volume']}")
                    
                    order_res = await broker.place_order(
                        symbol, decision.action, size_data["volume"],
                        stop_loss=size_data["stop_loss"],
                        take_profit=size_data["take_profit"]
                    )
                    
                    if "success" in order_res and order_res["success"]:
                        trade_executed = True
                        
                        # Save to DB
                        db_trade = await crud.create_trade(
                            db,
                            external_id=order_res.get("position_id", ""),
                            symbol=symbol,
                            direction=decision.action,
                            volume=size_data["volume"],
                            open_price=current_price,
                            stop_loss=size_data["stop_loss"],
                            take_profit=size_data["take_profit"],
                            trading_mode=settings.trading_mode.value,
                            metadata_json={"risk_amount": size_data["risk_amount"]}
                        )
                        trade_id = db_trade.id
                    else:
                        decision.reasoning += f" | Order failed: {order_res.get('error')}"
                else:
                    decision.reasoning += f" | Sizing failed: {size_data.get('reason')}"
            else:
                decision.action = "REJECT"
                decision.reasoning += f" | Risk blocked: {risk_check['reason']}"
                logger.warning(f"  ❌ Risk blocked {symbol}: {risk_check['reason']}")
                
        # 6. Save Decision Audit Trail
        await crud.create_decision(
            db,
            symbol=symbol,
            action=decision.action,
            confidence=decision.confidence,
            trading_mode=decision.mode_used,
            threshold_used=decision.threshold,
            reasoning=decision.reasoning,
            trade_id=trade_id,
            signals_json=[s.model_dump() for s in signals]
        )

# Global Instance
watcher = MarketWatcher()
