import asyncio
from typing import List, Dict, Any
from app.config import settings
from app.utils.logger import logger
from app.core.broker.metaapi_client import broker

class TrailingStopManager:
    """
    Manages Trailing Stop Loss logic for open positions.
    Phase 2 implementation:
    - Breakeven move: Once profit > 1x ATR, move SL to entry price.
    - ATR trail: Once at breakeven, maintain a 1.5x ATR distance from the price.
    """

    async def update_trailing_stops(self, open_positions: List[Dict[str, Any]], candle_cache: Dict[str, Dict[str, Any]]):
        """
        Check all open positions and adjust Stop Loss if needed.
        """
        if not settings.trailing_stop_enabled:
            return

        for pos in open_positions:
            symbol = pos.get("symbol")
            pos_id = pos.get("id")
            if not symbol or not pos_id:
                continue

            # Need ATR value for this symbol
            # We look it up in the candle cache (cached in MarketWatcher)
            # MarketWatcher.analyze returns raw indicators including ATR
            # But here we only have the candle_cache. We need to re-calc ATR or 
            # ideally MarketWatcher passes the latest indicators.
            # Simplified: if ATR isn't in cache, we skip.
            # In MarketWatcher we'll make sure to store ATR in the cache.
            
            cached_data = candle_cache.get(symbol)
            if not cached_data or "atr" not in cached_data:
                continue

            atr_val = cached_data["atr"]
            current_price = pos.get("currentPrice")
            open_price = pos.get("openPrice")
            current_sl = pos.get("stopLoss")
            direction = pos.get("type") # BUY or SELL

            if not current_price or not open_price:
                continue

            # 1. Calculate P&L in price distance
            is_buy = "BUY" in direction
            profit_dist = (current_price - open_price) if is_buy else (open_price - current_price)
            
            # 2. Breakeven Logic
            # If profit > ATR_mult and haven't moved to breakeven yet
            be_threshold = atr_val * settings.trailing_breakeven_atr_mult
            
            new_sl = None
            
            # Check if SL is already at or better than breakeven
            at_breakeven = False
            if current_sl:
                if is_buy:
                    at_breakeven = (current_sl >= open_price)
                else:
                    at_breakeven = (current_sl <= open_price)

            if not at_breakeven and profit_dist >= be_threshold:
                logger.info(f"🛡️ Moving {symbol} (pos:{pos_id}) to BREAKEVEN (Profit: {profit_dist:.5f} >= {be_threshold:.5f})")
                new_sl = open_price # Breakeven
            
            # 3. Trailing Logic (only after breakeven for safety)
            if at_breakeven:
                # Target SL = current_price - 1.5x ATR (for BUY)
                trail_dist = atr_val * settings.trailing_atr_mult
                target_sl = (current_price - trail_dist) if is_buy else (current_price + trail_dist)
                
                # Only move SL if it improves protection (tightens)
                if is_buy:
                    if target_sl > current_sl:
                        # Ensure we don't go below breakeven again
                        new_sl = max(target_sl, open_price)
                else:
                    if target_sl < current_sl:
                        new_sl = min(target_sl, open_price)

            if new_sl and round(new_sl, 5) != round(current_sl or 0, 5):
                # Apply the change via broker
                try:
                    # Round based on JPY
                    is_jpy = "JPY" in symbol
                    decimals = 3 if is_jpy else 5
                    final_sl = round(new_sl, decimals)
                    
                    if final_sl == round(current_sl or 0, decimals):
                        continue
                        
                    logger.info(f"📈 Trailing SL for {symbol} (pos:{pos_id}) -> {final_sl:.5f}")
                    await broker.modify_position(pos_id, stop_loss=final_sl)
                except Exception as e:
                    logger.error(f"Failed to update trailing SL for {pos_id}: {e}")

# Global instance
trailing_manager = TrailingStopManager()
