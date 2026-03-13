"""
Position Sizer — Dynamically calculate lot sizes and stop loss based on ATR and Risk limits.
"""
from typing import Dict, Any, Optional
from app.config import settings
from app.utils.logger import logger


class PositionSizer:
    """Calculates safe volume and stop loss for trades."""
    
    def __init__(self):
        pass
        
    def calculate(
        self,
        symbol: str, 
        direction: str,
        current_price: float,
        account_equity: float,
        atr_value: float,
        symbol_info: Dict[str, Any],
        confidence: float
    ) -> Dict[str, Any]:
        """
        Calculate Lot Size, Stop Loss, and Take Profit.
        """
        # Read from configuration (scaled by confidence/mode)
        base_risk_pct = settings.effective_max_risk_pct
        
        # We scale risk linearly by how confident the brain is (from min required threshold to 1.0)
        min_conf = settings.confidence_threshold
        if confidence < min_conf:
            confidence = min_conf  # Failsafe
            
        # Scale between 0.5 and 1.0 multiplier 
        # (Very confident = 1.0 * risk_pct. Barely confident = 0.5 * risk_pct)
        conf_multiplier = 0.5 + ((confidence - min_conf) / (1.0 - min_conf) * 0.5)
        risk_pct = base_risk_pct * conf_multiplier
        
        risk_amount = account_equity * (risk_pct / 100.0)
        
        # 1. Calculate Stop Loss distance using ATR (Average True Range)
        # Using 1.5x ATR for Stop Loss to avoid noise triggering
        sl_distance = atr_value * 1.5
        
        # Take Profit is typically 2x the risk distance (1:2 R:R ratio)
        tp_distance = sl_distance * 2.0
        
        # 2. Derive Lot Size
        # Value of 1 pip for standard lot
        contract_size = symbol_info.get("contract_size", 100000)
        point_value = symbol_info.get("point", 0.00001)

        # Fix for JPY pairs (e.g., USDJPY, EURJPY)
        # JPY pairs usually have 3 decimal places instead of 5
        is_jpy = "JPY" in symbol
        if is_jpy:
            point_value = max(point_value, 0.001)  # Ensure it's not 0.00001

        # Tick value = Pip value for 1 point * contract size
        # This is the value of 1 point movement in the QUOTE currency
        tick_value_quote = point_value * contract_size

        # Convert tick value to USD (Account Currency)
        tick_value_usd = tick_value_quote
        quote_ccy = symbol[3:]
        
        if quote_ccy != "USD":
            if is_jpy:
                # E.g., tick is in JPY. USDJPY rate is say 150.0. 
                # 1000 JPY / 150.0 = 6.66 USD
                tick_value_usd = tick_value_quote / current_price
            else:
                # E.g., EURGBP. Tick is in GBP. Need GBPUSD rate.
                # For simplicity, if we don't have the exact cross rate,
                # we approximate or assume it's roughly 1.0-1.3 for majors
                # In a full system, you'd fetch the GBPUSD price here.
                # We'll use a rough fallback if not JPY and not USD quote.
                tick_value_usd = tick_value_quote * 1.25

        # How many points is the stop loss?
        sl_points = sl_distance / point_value
        
        if sl_points <= 0:
            logger.error("Stop loss distance is zero")
            return {"allowed": False, "reason": "SL distance is zero"}
            
        # Volume calculation
        required_volume = risk_amount / (sl_points * tick_value_usd)
        
        # Apply symbol volume constraints
        min_vol = symbol_info.get("min_volume", 0.01)
        max_vol = symbol_info.get("max_volume", 100.0)
        vol_step = symbol_info.get("volume_step", 0.01)
        
        # Map required_volume to nearest vol_step
        steps = int(required_volume / vol_step)
        final_volume = steps * vol_step
        
        # Clamp between min & max
        final_volume = max(min_vol, min(max_vol, final_volume))
        
        # Calculate actual SL/TP prices
        # Round to correct decimals (3 for JPY, 5 for others)
        decimals = 3 if is_jpy else 5
        
        if direction == "BUY":
            sl_price = round(current_price - sl_distance, decimals)
            tp_price = round(current_price + tp_distance, decimals)
        else: # SELL
            sl_price = round(current_price + sl_distance, decimals)
            tp_price = round(current_price - tp_distance, decimals)
            
        logger.info(f"📐 Sizer for {symbol}: Risk={risk_amount:.2f}$, Vol={final_volume:.2f}, SL-Dist={sl_distance:.5f}")
        
        return {
            "allowed": True,
            "volume": round(final_volume, 2),
            "stop_loss": sl_price,
            "take_profit": tp_price,
            "risk_pct_used": round(risk_pct, 2),
            "risk_amount": round(risk_amount, 2)
        }


# Singleton
position_sizer = PositionSizer()
