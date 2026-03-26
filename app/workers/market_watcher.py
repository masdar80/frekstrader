"""
Market Watcher Background Worker.
Orchestrates the entire trading pipeline for all configured currency pairs.

v2 — Performance improvements:
  - 30-second analysis loop (down from 5 minutes)
  - Concurrent candle fetching per symbol (asyncio.gather)
  - Separate 15-minute timer for sentiment analysis (cached between runs)
  - Persistent peak_equity tracking via DB
"""
import asyncio
import time
from typing import List, Dict, Any, Optional

from app.config import settings
from app.utils.logger import logger
from app.core.broker.metaapi_client import broker
from app.core.analysis.technical import technical_analyzer
from app.core.analysis.sentiment import sentiment_engine
from app.core.analysis.signals import normalize_technical_signals, normalize_sentiment_signals
from app.core.analysis.calendar import economic_calendar
from app.core.brain.decision_engine import decision_engine
from app.core.risk.manager import risk_manager
from app.core.risk.position_sizer import position_sizer
from app.api.websocket import manager as ws_manager
from app.utils.helpers import utcnow

from app.db.database import async_session
from app.db import crud


class MarketWatcher:
    """Runs continuously, driving the trading bot logic."""

    def __init__(self):
        self.is_running = False
        self.is_paused = False
        self.sleep_interval = 60          # Run every 60 seconds (prevents 429)
        self.sentiment_interval = 900     # Refresh sentiment every 15 minutes
        self._last_sentiment_run = 0.0
        self._sentiment_cache: Dict[str, Dict[str, Any]] = {}
        self._candle_cache: Dict[str, Dict[str, Any]] = {}
        self._candle_cache_ttl = 300      # 5 minute candle cache
        self._peak_equity: float = 0.0    # Tracked persistently
        self._broker_semaphore = asyncio.Semaphore(3)  # Max 3 concurrent broker requests

    async def start(self):
        self.is_running = True
        logger.info("🚀 Market Watcher starting...")
        
        # Load peak equity from DB
        try:
            async with async_session() as db:
                latest_snap = await crud.get_latest_snapshot(db)
                if latest_snap and latest_snap.peak_equity:
                    self._peak_equity = latest_snap.peak_equity
                    logger.info(f"Loaded peak equity from DB: ${self._peak_equity:.2f}")
        except Exception as e:
            logger.error(f"Failed to load peak equity on startup: {e}")

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
        if self.is_paused:
            logger.info("⏸️ Market Watcher PAUSED. Skipping analysis cycle...")
            return

        logger.info(f"--- 🔄 Starting analysis cycle for {len(settings.pairs_list)} pairs ---")

        # 1. Fetch current account state
        account_info = await broker.get_account_info()
        open_positions = await broker.get_positions()

        # 1.5. Reconcile broker positions with DB open trades to detect closures
        await self._reconcile_positions(open_positions)

        # 2. Track peak equity properly (persist across restarts)
        current_equity = account_info.get("equity", 0)
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity

        async with async_session() as db:
            daily_pnl = await crud.get_daily_pnl(db)
            weekly_pnl = await crud.get_weekly_pnl(db)

            # Save account snapshot with real peak and drawdown
            drawdown_pct = 0.0
            if self._peak_equity > 0:
                drawdown_pct = ((self._peak_equity - current_equity) / self._peak_equity) * 100

            await crud.create_snapshot(
                db,
                balance=account_info.get("balance", 0),
                equity=current_equity,
                margin=account_info.get("margin", 0),
                free_margin=account_info.get("free_margin", 0),
                open_positions=len(open_positions),
                daily_pnl=daily_pnl,
                peak_equity=self._peak_equity,
                drawdown_pct=round(drawdown_pct, 2),
            )
            await db.commit()

        # 3. Check if sentiment needs refreshing (every 15 min)
        now = time.time()
        if now - self._last_sentiment_run > self.sentiment_interval:
            logger.info("📰 Refreshing sentiment for all pairs...")
            await self._refresh_all_sentiment()
            self._last_sentiment_run = now

        # 4. Process all pairs SEQUENTIALLY with delays (to prevent 429)
        for symbol in settings.pairs_list:
            if not self.is_running or self.is_paused:
                break
                
            try:
                await self._analyze_and_trade_symbol(
                    symbol, account_info, open_positions,
                    daily_pnl, weekly_pnl, self._peak_equity
                )
                # Small stagger delay between symbols
                await asyncio.sleep(2.0)
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")

        logger.info("--- ✅ Analysis cycle complete ---")

    async def _refresh_all_sentiment(self):
        """Fetch fresh sentiment for all currencies (runs every 15 min)."""
        if not settings.use_ai_sentiment:
            return
            
        for symbol in settings.pairs_list:
            try:
                self._sentiment_cache[symbol] = await sentiment_engine.get_sentiment(symbol)
            except Exception as e:
                logger.error(f"Sentiment fetch error for {symbol}: {e}")
            await asyncio.sleep(0.5)  # Small delay to avoid rate limits

    async def _analyze_and_trade_symbol(
        self, symbol: str, account_info, open_positions,
        daily_pnl, weekly_pnl, peak_equity
    ):
        """The core pipeline for a single currency pair."""
        logger.info(f"🔎 Analyzing {symbol}...")

        # 1. Fetch Market Data — use cache for candles
        async with self._broker_semaphore:
            current_price_data = await broker.get_price(symbol)
            if not current_price_data:
                logger.warning(f"Failed to fetch current price for {symbol}")
                return

        # Handle candle caching (only fetch if expired)
        now = time.time()
        cached_data = self._candle_cache.get(symbol)
        
        if cached_data and (now - cached_data["timestamp"] < self._candle_cache_ttl):
            logger.info(f"  📦 Using cached candles for {symbol}")
            candles_by_tf = cached_data["candles"]
        else:
            logger.info(f"  📥 Fetching fresh candles for {symbol}...")
            async with self._broker_semaphore:
                candle_tasks = {
                    tf: broker.get_candles(symbol, timeframe=tf, count=200)
                    for tf in technical_analyzer.TIMEFRAMES
                }
                candle_results = await asyncio.gather(*candle_tasks.values(), return_exceptions=True)
                candles_by_tf = {}
                for tf, result in zip(candle_tasks.keys(), candle_results):
                    if isinstance(result, list):
                        candles_by_tf[tf] = result
                    else:
                        logger.warning(f"Candle fetch failed for {symbol}/{tf}: {result}")
                
                # Update cache
                self._candle_cache[symbol] = {
                    "timestamp": now,
                    "candles": candles_by_tf
                }

        current_price = current_price_data["ask"]
        bid_price = current_price_data.get("bid", current_price)
        current_spread = current_price - bid_price

        symbol_info = await broker.get_symbol_info(symbol)

        # 2. Technical Analysis
        ta_raw_results = technical_analyzer.analyze(candles_by_tf)
        ta_confluence = technical_analyzer.get_confluence_score(ta_raw_results)

        # 4. Sentiment — use cached results (refreshed on separate timer)
        sentiment_result = self._sentiment_cache.get(symbol, {
            "symbol": symbol, "signal": "NEUTRAL", "score": 0.0,
            "strength": 0.0, "confidence": 0.0,
            "base": {"score": 0.0, "news_count": 0},
            "quote": {"score": 0.0, "news_count": 0},
        })

        # Normalize Signals
        signals = [
            normalize_technical_signals(symbol, ta_confluence)
        ]
        
        if settings.use_ai_sentiment:
            signals.append(normalize_sentiment_signals(symbol, sentiment_result))

        # Perform the DB operations in a fresh session
        async with async_session() as db:
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
            risk_check = None
            size_data = None

            if decision.action in ["BUY", "SELL"]:
                # Check Spread (protect against news spikes)
                typical_spread_points = symbol_info.get("spread", 0)
                point_value = symbol_info.get("point", 0.00001)
                current_spread_points = current_spread / point_value if point_value else 0
                
                spread_ok = True
                if current_spread_points > max(50, typical_spread_points * 2):
                    spread_ok = False
                    decision.action = "REJECT"
                    decision.reasoning += f" | Spread too high: {current_spread_points:.1f} pts (typical: {typical_spread_points})"
                    logger.warning(f"  ❌ Spread blocked {symbol}: {current_spread_points:.1f} pts")

                if spread_ok:
                    # Check Economic Calendar
                    calendar_check = await economic_calendar.is_safe_to_trade(symbol)
                    if not calendar_check["safe"]:
                        decision.action = "REJECT"
                        decision.reasoning += f" | Calendar blocked: {calendar_check['reason']}"
                        logger.warning(f"  ❌ Calendar blocked {symbol}: {calendar_check['reason']}")
                    else:
                        # Check Risk
                        risk_check = risk_manager.check_trade_allowed(
                            symbol, decision.action, account_info, open_positions,
                            daily_pnl, weekly_pnl, peak_equity
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
                                logger.critical(
                                    f"🚀 EXECUTING {decision.action} onto {symbol} "
                                    f"| Vol: {size_data['volume']}"
                                )

                                order_res = await broker.place_order(
                                    symbol, decision.action, size_data["volume"],
                                    stop_loss=size_data["stop_loss"],
                                    take_profit=size_data["take_profit"]
                                )

                                if "success" in order_res and order_res["success"]:
                                    trade_executed = True
                                    
                                    # Post-Execution Verification
                                    await asyncio.sleep(1.0) # Wait for broker to settle position
                                    new_positions = await broker.get_positions(use_cache=False)
                                    pos_id = order_res.get("position_id")
                                    actual_fill_price = current_price
                                    
                                    if pos_id:
                                        matching_pos = next((p for p in new_positions if p.get("id") == pos_id), None)
                                        if matching_pos:
                                            actual_fill_price = matching_pos.get("openPrice", current_price)
                                            # Calculate slippage in pips
                                            is_jpy = "JPY" in symbol
                                            pip_multiplier = 100 if is_jpy else 10000
                                            slippage_pips = abs(actual_fill_price - current_price) * pip_multiplier
                                            
                                            if slippage_pips > settings.max_slippage_pips:
                                                logger.critical(f"⚠️ HIGH SLIPPAGE DETECTED on {symbol}: Expected {current_price:.5f}, Filled {actual_fill_price:.5f} ({slippage_pips:.1f} pips)")
                                                decision.reasoning += f" | Slippage Alert: {slippage_pips:.1f} pips"
                                            
                                            # Verify SL and TP were set
                                            if not matching_pos.get("stopLoss") or not matching_pos.get("takeProfit"):
                                                logger.critical(f"⚠️ MISSING SL/TP on {symbol} position {pos_id}")

                                    # Save to DB
                                    db_trade = await crud.create_trade(
                                        db,
                                        external_id=order_res.get("position_id", ""),
                                        symbol=symbol,
                                        direction=decision.action,
                                        volume=size_data["volume"],
                                        open_price=actual_fill_price,
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
                                decision.action = "REJECT"
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

            # 7. Commit immediately for real-time visibility
            await db.commit()

        # 8. Broadcast to frontend
        logger.info(f"  📡 Broadcasting {symbol} {decision.action} to dashboard...")
        await ws_manager.broadcast_decision({
            "symbol": symbol,
            "action": decision.action,
            "confidence": decision.confidence,
            "reasoning": decision.reasoning,
            "timestamp": utcnow().isoformat(),
            "ai_active": settings.use_ai_sentiment,
            "indicators": ta_confluence.get("breakdown", []),
            "sentiment": sentiment_result,
            "risk_check": risk_check if decision.action in ["BUY", "SELL"] else None,
            "sizing": size_data if trade_executed else None
        })

    async def _reconcile_positions(self, open_positions: List[Dict[str, Any]]):
        """Reconcile broker positions with DB open trades to detect closures."""
        broker_position_ids = {p.get("id") for p in open_positions if p.get("id")}
        
        async with async_session() as db:
            open_db_trades = await crud.get_open_trades_by_external_id(db)
            
            # Fetch history only if there's a discrepancy
            history = None
            
            for ext_id, trade in open_db_trades.items():
                if ext_id not in broker_position_ids:
                    logger.info(f"🔄 Reconciling closed trade: {trade.symbol} (ID: {ext_id})")
                    
                    if history is None:
                        history = await broker.get_history(days=3)
                        
                    # MT5: A position can have multiple deals (Entry In, Entry Out).
                    # We must sum them all to get the true P&L.
                    matching_deals = [d for d in history if d.get("position_id") == ext_id]
                    
                    profit = 0.0
                    close_price = 0.0
                    
                    if matching_deals:
                        for deal in matching_deals:
                            profit += deal.get("profit", 0.0) + deal.get("swap", 0.0) + deal.get("commission", 0.0)
                            # The close price is from the DEAL_ENTRY_OUT or DEAL_ENTRY_INOUT
                            if deal.get("entry_type") in ["DEAL_ENTRY_OUT", "DEAL_ENTRY_INOUT"]:
                                close_price = deal.get("price", 0.0)
                        
                        # Fallback for close price if deal entry type mapping is missing
                        if close_price == 0.0:
                            close_price = matching_deals[-1].get("price", 0.0)
                            
                        logger.info(f"  💰 Found {len(matching_deals)} deals for {trade.symbol}: Total Profit ${profit:.2f} at price {close_price}")
                    else:
                        logger.warning(f"  ❌ Could not find history deal for position {ext_id}. Marking as closed with 0 profit.")

                        
                    await crud.close_trade(db, trade.id, close_price, profit)
                    await crud.update_decision_outcome(db, trade.id, profit > 0)
                    
            await db.commit()

    def pause(self):
        """Pauses the market watcher analysis loop."""
        self.is_paused = True
        logger.critical("🛑 EMERGENCY PAUSE TRIGGERED! Trading halted.")

    def resume(self):
        """Resumes the market watcher analysis loop."""
        self.is_paused = False
        logger.info("▶️ Trading Resumed.")

    async def emergency_close_all(self):
        """Closes all open positions and pauses the bot."""
        self.pause()
        logger.critical("🚨 EMERGENCY CLOSE ALL TRIGGERED! Closing all open positions...")
        open_positions = await broker.get_positions()
        for pos in open_positions:
            try:
                pos_id = pos.get("id")
                symbol = pos.get("symbol")
                if pos_id:
                    logger.critical(f"Closing position {pos_id} for {symbol}...")
                    res = await broker.close_position(pos_id)
                    if not res.get("success"):
                        logger.error(f"Failed to close position {pos_id}: {res.get('error')}")
            except Exception as e:
                logger.error(f"Error during emergency close of position {pos.get('id')}: {e}")

# Global Instance
watcher = MarketWatcher()
