"""
Technical Analysis Engine — Multi-timeframe indicator calculations.
Uses pandas-ta to compute RSI, MACD, EMA, Bollinger Bands, ATR, Stochastic, ADX.
"""
import pandas as pd
import pandas_ta as ta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from app.utils.logger import logger


@dataclass
class IndicatorResult:
    """Result from a single indicator calculation."""
    name: str
    timeframe: str
    value: float
    signal: str  # BUY, SELL, NEUTRAL
    strength: float  # 0.0 to 1.0
    details: Dict[str, Any] = field(default_factory=dict)


class TechnicalAnalyzer:
    """Multi-timeframe technical analysis engine."""

    TIMEFRAMES = ["15m", "1h", "4h", "1d"]
    TIMEFRAME_WEIGHTS = {"15m": 0.15, "1h": 0.25, "4h": 0.30, "1d": 0.30}

    def __init__(self):
        pass

    def analyze(self, candles_by_tf: Dict[str, List[Dict]]) -> Dict[str, List[IndicatorResult]]:
        """
        Run all indicators across multiple timeframes.
        candles_by_tf: {"1h": [{"open": ..., "high": ..., ...}, ...], "4h": [...]}
        Returns: {"RSI": [IndicatorResult, ...], "MACD": [...], ...}
        """
        all_results = {}

        for tf, candles in candles_by_tf.items():
            if not candles or len(candles) < 50:
                logger.warning(f"Not enough candles for {tf} (got {len(candles)})")
                continue

            df = self._candles_to_df(candles)
            if df is None or len(df) < 50:
                continue

            results = self._compute_all_indicators(df, tf)
            for result in results:
                if result.name not in all_results:
                    all_results[result.name] = []
                all_results[result.name].append(result)

        return all_results

    def _candles_to_df(self, candles: List[Dict]) -> Optional[pd.DataFrame]:
        """Convert candle dicts to DataFrame."""
        try:
            df = pd.DataFrame(candles)
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df.dropna(subset=["open", "high", "low", "close"], inplace=True)
            return df
        except Exception as e:
            logger.error(f"Failed to create DataFrame: {e}")
            return None

    def _compute_all_indicators(self, df: pd.DataFrame, timeframe: str) -> List[IndicatorResult]:
        """Compute all indicators for a single timeframe."""
        results = []

        results.append(self._calc_rsi(df, timeframe))
        results.append(self._calc_macd(df, timeframe))
        results.extend(self._calc_ema(df, timeframe))
        results.append(self._calc_bollinger(df, timeframe))
        results.append(self._calc_atr(df, timeframe))
        results.append(self._calc_stochastic(df, timeframe))
        results.append(self._calc_adx(df, timeframe))

        return [r for r in results if r is not None]

    def _calc_rsi(self, df: pd.DataFrame, tf: str, length: int = 14) -> Optional[IndicatorResult]:
        """RSI — Momentum oscillator. <30 oversold, >70 overbought."""
        try:
            rsi = ta.rsi(df["close"], length=length)
            if rsi is None or rsi.empty:
                return None
            val = float(rsi.iloc[-1])

            if val < 30:
                signal, strength = "BUY", min(1.0, (30 - val) / 30)
            elif val > 70:
                signal, strength = "SELL", min(1.0, (val - 70) / 30)
            else:
                signal, strength = "NEUTRAL", 0.0

            return IndicatorResult(
                name="RSI", timeframe=tf, value=round(val, 2),
                signal=signal, strength=round(strength, 3),
                details={"period": length, "prev_value": round(float(rsi.iloc[-2]), 2) if len(rsi) > 1 else None}
            )
        except Exception as e:
            logger.error(f"RSI calculation failed: {e}")
            return None

    def _calc_macd(self, df: pd.DataFrame, tf: str) -> Optional[IndicatorResult]:
        """MACD — Trend following. Crossover signals."""
        try:
            macd_df = ta.macd(df["close"], fast=12, slow=26, signal=9)
            if macd_df is None or macd_df.empty:
                return None

            macd_line = float(macd_df.iloc[-1, 0])  # MACD line
            signal_line = float(macd_df.iloc[-1, 2])  # Signal line
            histogram = float(macd_df.iloc[-1, 1])  # Histogram

            prev_hist = float(macd_df.iloc[-2, 1]) if len(macd_df) > 1 else 0

            # Crossover detection
            if histogram > 0 and prev_hist <= 0:
                signal, strength = "BUY", 0.8
            elif histogram < 0 and prev_hist >= 0:
                signal, strength = "SELL", 0.8
            elif histogram > 0:
                signal, strength = "BUY", min(0.6, abs(histogram) * 100)
            elif histogram < 0:
                signal, strength = "SELL", min(0.6, abs(histogram) * 100)
            else:
                signal, strength = "NEUTRAL", 0.0

            return IndicatorResult(
                name="MACD", timeframe=tf, value=round(histogram, 6),
                signal=signal, strength=round(strength, 3),
                details={"macd": round(macd_line, 6), "signal": round(signal_line, 6), "histogram": round(histogram, 6)}
            )
        except Exception as e:
            logger.error(f"MACD calculation failed: {e}")
            return None

    def _calc_ema(self, df: pd.DataFrame, tf: str) -> List[IndicatorResult]:
        """EMA (20, 50, 200) — Trend direction and crossovers."""
        results = []
        try:
            ema20 = ta.ema(df["close"], length=20)
            ema50 = ta.ema(df["close"], length=50)
            ema200 = ta.ema(df["close"], length=200) if len(df) >= 200 else None

            current_price = float(df["close"].iloc[-1])

            if ema20 is not None and ema50 is not None and not ema20.empty and not ema50.empty:
                e20 = float(ema20.iloc[-1])
                e50 = float(ema50.iloc[-1])

                # Golden cross (EMA20 > EMA50) / Death cross
                if e20 > e50 and current_price > e20:
                    signal, strength = "BUY", 0.7
                elif e20 < e50 and current_price < e20:
                    signal, strength = "SELL", 0.7
                elif current_price > e20:
                    signal, strength = "BUY", 0.4
                elif current_price < e20:
                    signal, strength = "SELL", 0.4
                else:
                    signal, strength = "NEUTRAL", 0.0

                results.append(IndicatorResult(
                    name="EMA_CROSS", timeframe=tf, value=round(e20, 6),
                    signal=signal, strength=round(strength, 3),
                    details={"ema20": round(e20, 6), "ema50": round(e50, 6), "price": current_price}
                ))

            # EMA200 trend
            if ema200 is not None and not ema200.empty:
                e200 = float(ema200.iloc[-1])
                if current_price > e200:
                    signal, strength = "BUY", 0.5
                else:
                    signal, strength = "SELL", 0.5

                results.append(IndicatorResult(
                    name="EMA200_TREND", timeframe=tf, value=round(e200, 6),
                    signal=signal, strength=round(strength, 3),
                    details={"ema200": round(e200, 6), "price": current_price}
                ))

        except Exception as e:
            logger.error(f"EMA calculation failed: {e}")
        return results

    def _calc_bollinger(self, df: pd.DataFrame, tf: str) -> Optional[IndicatorResult]:
        """Bollinger Bands — Volatility and reversal zones."""
        try:
            bb = ta.bbands(df["close"], length=20, std=2)
            if bb is None or bb.empty:
                return None

            # pandas-ta bbands returns columns: BBL_20_2.0, BBM_20_2.0, BBU_20_2.0, BBB_20_2.0, BBP_20_2.0
            # Use column name matching for safety
            bb_cols = bb.columns.tolist()
            lower_col = [c for c in bb_cols if c.startswith("BBL")][0]
            middle_col = [c for c in bb_cols if c.startswith("BBM")][0]
            upper_col = [c for c in bb_cols if c.startswith("BBU")][0]

            lower = float(bb[lower_col].iloc[-1])
            middle = float(bb[middle_col].iloc[-1])
            upper = float(bb[upper_col].iloc[-1])
            price = float(df["close"].iloc[-1])

            band_width = upper - lower
            if band_width == 0:
                return None

            position = (price - lower) / band_width  # 0 = at lower, 1 = at upper

            if position <= 0.1:
                signal, strength = "BUY", 0.8  # Near lower band = oversold
            elif position >= 0.9:
                signal, strength = "SELL", 0.8  # Near upper band = overbought
            elif position < 0.3:
                signal, strength = "BUY", 0.4
            elif position > 0.7:
                signal, strength = "SELL", 0.4
            else:
                signal, strength = "NEUTRAL", 0.0

            return IndicatorResult(
                name="BBANDS", timeframe=tf, value=round(position, 3),
                signal=signal, strength=round(strength, 3),
                details={"upper": round(upper, 6), "middle": round(middle, 6),
                         "lower": round(lower, 6), "position": round(position, 3)}
            )
        except Exception as e:
            logger.error(f"Bollinger calculation failed: {e}")
            return None

    def _calc_atr(self, df: pd.DataFrame, tf: str, length: int = 14) -> Optional[IndicatorResult]:
        """ATR — Average True Range for volatility / stop-loss sizing."""
        try:
            atr = ta.atr(df["high"], df["low"], df["close"], length=length)
            if atr is None or atr.empty:
                return None
            val = float(atr.iloc[-1])

            # ATR doesn't give direction, but measures volatility
            return IndicatorResult(
                name="ATR", timeframe=tf, value=round(val, 6),
                signal="NEUTRAL", strength=0.0,
                details={"atr": round(val, 6), "atr_pips": round(val * 10000, 1)}
            )
        except Exception as e:
            logger.error(f"ATR calculation failed: {e}")
            return None

    def _calc_stochastic(self, df: pd.DataFrame, tf: str) -> Optional[IndicatorResult]:
        """Stochastic Oscillator — Overbought/oversold confirmation."""
        try:
            stoch = ta.stoch(df["high"], df["low"], df["close"], k=14, d=3)
            if stoch is None or stoch.empty:
                return None

            k_val = float(stoch.iloc[-1, 0])
            d_val = float(stoch.iloc[-1, 1])

            if k_val < 20 and d_val < 20:
                signal, strength = "BUY", 0.7
            elif k_val > 80 and d_val > 80:
                signal, strength = "SELL", 0.7
            elif k_val < 30:
                signal, strength = "BUY", 0.4
            elif k_val > 70:
                signal, strength = "SELL", 0.4
            else:
                signal, strength = "NEUTRAL", 0.0

            return IndicatorResult(
                name="STOCH", timeframe=tf, value=round(k_val, 2),
                signal=signal, strength=round(strength, 3),
                details={"k": round(k_val, 2), "d": round(d_val, 2)}
            )
        except Exception as e:
            logger.error(f"Stochastic calculation failed: {e}")
            return None

    def _calc_adx(self, df: pd.DataFrame, tf: str, length: int = 14) -> Optional[IndicatorResult]:
        """ADX — Trend strength indicator. >25 = strong trend."""
        try:
            adx_df = ta.adx(df["high"], df["low"], df["close"], length=length)
            if adx_df is None or adx_df.empty:
                return None

            # pandas-ta adx returns columns: ADX_14, DMP_14, DMN_14
            # Use column name matching for safety
            adx_cols = adx_df.columns.tolist()
            adx_col = [c for c in adx_cols if c.startswith("ADX")][0]
            dmp_col = [c for c in adx_cols if c.startswith("DMP")][0]
            dmn_col = [c for c in adx_cols if c.startswith("DMN")][0]

            adx_val = float(adx_df[adx_col].iloc[-1])
            plus_di = float(adx_df[dmp_col].iloc[-1])
            minus_di = float(adx_df[dmn_col].iloc[-1])

            if adx_val > 25:
                if plus_di > minus_di:
                    signal, strength = "BUY", min(1.0, adx_val / 50)
                else:
                    signal, strength = "SELL", min(1.0, adx_val / 50)
            else:
                signal, strength = "NEUTRAL", 0.0

            return IndicatorResult(
                name="ADX", timeframe=tf, value=round(adx_val, 2),
                signal=signal, strength=round(strength, 3),
                details={"adx": round(adx_val, 2), "plus_di": round(plus_di, 2), "minus_di": round(minus_di, 2)}
            )
        except Exception as e:
            logger.error(f"ADX calculation failed: {e}")
            return None

    def get_confluence_score(self, results: Dict[str, List[IndicatorResult]]) -> Dict[str, Any]:
        """
        Calculate confluence: how many indicators agree on direction.
        Returns overall direction, confidence, and breakdown.
        """
        buy_votes = 0
        sell_votes = 0
        total_weight = 0
        buy_strength = 0.0
        sell_strength = 0.0
        breakdown = []

        for indicator_name, indicator_results in results.items():
            for result in indicator_results:
                if result.signal == "NEUTRAL":
                    continue

                tf_weight = self.TIMEFRAME_WEIGHTS.get(result.timeframe, 0.2)

                if result.signal == "BUY":
                    buy_votes += 1
                    buy_strength += result.strength * tf_weight
                elif result.signal == "SELL":
                    sell_votes += 1
                    sell_strength += result.strength * tf_weight

                total_weight += tf_weight
                breakdown.append({
                    "indicator": result.name,
                    "timeframe": result.timeframe,
                    "signal": result.signal,
                    "strength": result.strength,
                    "value": result.value,
                })

        # Normalize
        if total_weight > 0:
            buy_confidence = buy_strength / total_weight
            sell_confidence = sell_strength / total_weight
        else:
            buy_confidence = sell_confidence = 0.0

        if buy_votes > sell_votes and buy_confidence > 0.1:
            direction = "BUY"
            confidence = buy_confidence
        elif sell_votes > buy_votes and sell_confidence > 0.1:
            direction = "SELL"
            confidence = sell_confidence
        else:
            direction = "NEUTRAL"
            confidence = 0.0

        total_signals = buy_votes + sell_votes
        agreement_ratio = max(buy_votes, sell_votes) / max(total_signals, 1)

        return {
            "direction": direction,
            "confidence": round(confidence, 3),
            "buy_votes": buy_votes,
            "sell_votes": sell_votes,
            "total_signals": total_signals,
            "agreement_ratio": round(agreement_ratio, 3),
            "contradictory": buy_votes > 0 and sell_votes > 0 and agreement_ratio < 0.6,
            "breakdown": breakdown,
        }


# Singleton
technical_analyzer = TechnicalAnalyzer()
