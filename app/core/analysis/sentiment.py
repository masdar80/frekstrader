"""
News Sentiment Engine using NewsAPI and Gemini/Vader.

v2 — Improvements:
  - Gemini returns structured JSON scores (used as primary scorer)
  - VADER is the fallback when Gemini is unavailable
  - Built-in TTL cache to avoid redundant API calls
"""
import json
import asyncio
import time
from typing import Dict, Any, List
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import google.generativeai as genai
import httpx

from app.config import settings
from app.utils.logger import logger


# In-memory TTL cache for sentiment results
_sentiment_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl = 900  # 15 minutes


class SentimentEngine:
    """Fetches news and calculates sentiment scores."""

    def __init__(self):
        self.vader = SentimentIntensityAnalyzer()
        self.newsapi_key = settings.news_api_key

        # Configure Gemini if available
        self.gemini_available = False
        if settings.gemini_api_key:
            try:
                genai.configure(api_key=settings.gemini_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-2.0-flash')
                self.gemini_available = True
                logger.info("✅ Gemini AI configured for advanced sentiment analysis")
            except Exception as e:
                logger.warning(f"Failed to configure Gemini: {e}")

        # Currency mapping for search terms
        self.currency_keywords = {
            "USD": ["USD", "US Dollar", "Federal Reserve", "US economy", "Powell", "FOMC", "NFP", "US CPI"],
            "EUR": ["EUR", "Euro", "ECB", "Eurozone", "Lagarde", "European economy"],
            "GBP": ["GBP", "British Pound", "BOE", "UK economy", "Bank of England", "Bailey"],
            "JPY": ["JPY", "Japanese Yen", "BOJ", "Bank of Japan", "Ueda", "Japan economy"],
            "AUD": ["AUD", "Australian Dollar", "RBA", "Reserve Bank of Australia", "Australia economy"],
            "CHF": ["CHF", "Swiss Franc", "SNB", "Swiss National Bank"],
        }

    async def get_sentiment(self, symbol: str) -> Dict[str, Any]:
        """Get overall sentiment for a trading pair (e.g., EURUSD).
        Uses cache to avoid redundant API calls within 15 minutes.
        """
        # Check cache
        cache_key = symbol
        cached = _sentiment_cache.get(cache_key)
        if cached and (time.time() - cached.get("_cached_at", 0)) < _cache_ttl:
            return cached

        base_ccy = symbol[:3]
        quote_ccy = symbol[3:]

        base_sentiment = await self._analyze_currency_news(base_ccy)
        quote_sentiment = await self._analyze_currency_news(quote_ccy)

        # Net sentiment: relative strength of base vs quote
        net_score = base_sentiment["score"] - quote_sentiment["score"]

        # Clamp between -1.0 and 1.0
        net_score = max(-1.0, min(1.0, net_score))

        if net_score > 0.3:
            signal = "BUY"
        elif net_score < -0.3:
            signal = "SELL"
        else:
            signal = "NEUTRAL"

        logger.info(
            f"📰 Sentiment for {symbol}: {signal} "
            f"(Base: {base_sentiment['score']:.2f}, "
            f"Quote: {quote_sentiment['score']:.2f}, Net: {net_score:.2f})"
        )

        result = {
            "symbol": symbol,
            "signal": signal,
            "score": net_score,
            "strength": abs(net_score),
            "base": base_sentiment,
            "quote": quote_sentiment,
            "confidence": min(1.0, (base_sentiment["news_count"] + quote_sentiment["news_count"]) / 10.0),
            "_cached_at": time.time(),
        }

        # Store in cache
        _sentiment_cache[cache_key] = result
        return result

    async def _analyze_currency_news(self, currency: str) -> Dict[str, Any]:
        """Fetch and analyze news for a specific currency."""
        articles = await self._fetch_newsapi(currency)

        if not articles:
            return {
                "currency": currency, "score": 0.0, "news_count": 0,
                "articles": [], "reasoning": "No recent news found."
            }

        # ── Strategy: Try Gemini first (structured JSON), fallback to VADER ──
        ai_score = None
        ai_reasoning = None

        if self.gemini_available and settings.use_ai_sentiment and len(articles) > 0:
            ai_score, ai_reasoning = await self._gemini_score(currency, articles)

        if ai_score is not None:
            # AI scored successfully — use it as primary
            analyzed_articles = [
                {"title": a.get("title", ""), "score": ai_score, "url": a.get("url", "")}
                for a in articles[:5]
            ]
            return {
                "currency": currency,
                "score": ai_score,
                "news_count": len(articles),
                "articles": analyzed_articles,
                "reasoning": ai_reasoning or "Gemini AI analysis",
                "source": "gemini",
            }

        # ── Fallback: VADER keyword scoring ──
        scores = []
        analyzed_articles = []

        for article in articles:
            title = article.get("title", "")
            description = article.get("description", "") or ""
            text_to_analyze = f"{title}. {description}"

            vs = self.vader.polarity_scores(text_to_analyze)
            compound_score = vs['compound']

            # Forex-specific keyword adjustments
            text_lower = text_to_analyze.lower()
            if "hawkish" in text_lower or "rate hike" in text_lower:
                compound_score += 0.3
            if "dovish" in text_lower or "rate cut" in text_lower or "recession" in text_lower:
                compound_score -= 0.3

            compound_score = max(-1.0, min(1.0, compound_score))

            scores.append(compound_score)
            analyzed_articles.append({
                "title": title,
                "score": compound_score,
                "url": article.get("url", "")
            })

        avg_score = sum(scores) / len(scores) if scores else 0.0

        return {
            "currency": currency,
            "score": avg_score,
            "news_count": len(articles),
            "articles": analyzed_articles[:5],
            "reasoning": f"VADER sentiment: {avg_score:+.2f} from {len(articles)} articles",
            "source": "vader",
        }

    async def _gemini_score(
        self, currency: str, articles: List[Dict]
    ) -> tuple:
        """Ask Gemini to return a structured sentiment score.
        Returns (score, reasoning) or (None, None) on failure.
        """
        try:
            headlines = "\n".join([f"- {a['title']}" for a in articles[:12]])
            prompt = (
                f"You are a professional forex analyst. "
                f"Analyze the financial sentiment of these news headlines "
                f"regarding the {currency} currency.\n\n"
                f"Headlines:\n{headlines}\n\n"
                f"Return ONLY valid JSON in this exact format, nothing else:\n"
                f'{{"score": <float between -1.0 and 1.0>, '
                f'"confidence": <float between 0.0 and 1.0>, '
                f'"reasoning": "<one sentence explanation>"}}\n\n'
                f"Where score: -1.0 = very bearish for {currency}, "
                f"+1.0 = very bullish for {currency}, 0.0 = neutral."
            )

            response = await asyncio.wait_for(
                asyncio.to_thread(self.gemini_model.generate_content, prompt),
                timeout=10.0  # 10 second timeout
            )

            text = response.text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            data = json.loads(text)
            score = max(-1.0, min(1.0, float(data.get("score", 0.0))))
            reasoning = data.get("reasoning", "AI analysis")

            logger.info(f"🤖 Gemini {currency}: score={score:+.2f} — {reasoning}")
            return score, reasoning

        except asyncio.TimeoutError:
            logger.warning(f"Gemini timeout for {currency}, falling back to VADER")
            return None, None
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Gemini parse error for {currency}: {e}")
            return None, None
        except Exception as e:
            logger.warning(f"Gemini failed for {currency}: {e}")
            return None, None

    async def _fetch_newsapi(self, currency: str) -> List[Dict[str, Any]]:
        """Fetch latest forex news from NewsAPI."""
        if not self.newsapi_key:
            return []

        keywords = self.currency_keywords.get(currency, [currency])
        query = " OR ".join([f'"{kw}"' for kw in keywords])
        formatted_query = quote_plus(f"({query}) AND (forex OR economy OR rates OR inflation OR bank)")

        # Last 24 hours
        from_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')

        url = (
            f"https://newsapi.org/v2/everything"
            f"?q={formatted_query}&from={from_date}"
            f"&language=en&sortBy=publishedAt&apiKey={self.newsapi_key}"
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    return data.get("articles", [])[:15]
                elif response.status_code == 426:
                    logger.warning("NewsAPI upgrade required (free plan restriction).")
                    return []
                else:
                    logger.warning(f"NewsAPI error: {response.status_code} - {response.text[:200]}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch news from NewsAPI: {e}")
            return []

# Singleton
sentiment_engine = SentimentEngine()
