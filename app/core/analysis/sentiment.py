"""
News Sentiment Engine using NewsAPI and Gemini/Vader.
"""
import ssl
import json
import asyncio
from typing import Dict, Any, List
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import google.generativeai as genai

from app.config import settings
from app.utils.logger import logger

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
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
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
        """Get overall sentiment for a trading pair (e.g., EURUSD)."""
        base_ccy = symbol[:3]
        quote_ccy = symbol[3:]

        base_sentiment = await self._analyze_currency_news(base_ccy)
        quote_sentiment = await self._analyze_currency_news(quote_ccy)

        # Net sentiment: relative strength of base vs quote
        # E.g., if EUR is +0.5 and USD is -0.3, EURUSD sentiment is +0.8 (Bullish)
        net_score = base_sentiment["score"] - quote_sentiment["score"]
        
        # Clamp between -1.0 and 1.0
        net_score = max(-1.0, min(1.0, net_score))

        if net_score > 0.3:
            signal = "BUY"
        elif net_score < -0.3:
            signal = "SELL"
        else:
            signal = "NEUTRAL"

        logger.info(f"📰 Sentiment for {symbol}: {signal} (Base: {base_sentiment['score']:.2f}, Quote: {quote_sentiment['score']:.2f}, Net: {net_score:.2f})")

        return {
            "symbol": symbol,
            "signal": signal,
            "score": net_score,
            "strength": abs(net_score),
            "base": base_sentiment,
            "quote": quote_sentiment,
            "confidence": min(1.0, (base_sentiment["news_count"] + quote_sentiment["news_count"]) / 10.0),
        }

    async def _analyze_currency_news(self, currency: str) -> Dict[str, Any]:
        """Fetch and analyze news for a specific currency."""
        articles = await self._fetch_newsapi(currency)
        
        if not articles:
            return {"currency": currency, "score": 0.0, "news_count": 0, "articles": [], "reasoning": "No recent news found."}

        scores = []
        analyzed_articles = []
        
        # Try to use Gemini for an aggregate summary if available
        summary_reasoning = "Analyzed using VADER sentiment."
        
        if self.gemini_available and len(articles) > 0:
            try:
                headlines = "\n".join([f"- {a['title']}" for a in articles[:10]])
                prompt = (
                    f"Analyze the financial sentiment of these recent news headlines regarding the {currency} currency. "
                    f"Is the overall outlook bullish (positive for the currency) or bearish (negative)? "
                    f"Provide a brief 2-sentence explanation.\n\nHeadlines:\n{headlines}"
                )
                response = await asyncio.to_thread(self.gemini_model.generate_content, prompt)
                summary_reasoning = response.text.replace('\n', ' ').strip()
            except Exception as e:
                logger.warning(f"Gemini sentiment summary failed: {e}")

        for article in articles:
            title = article.get("title", "")
            description = article.get("description", "") or ""
            text_to_analyze = f"{title}. {description}"
            
            # Base VADER scoring
            vs = self.vader.polarity_scores(text_to_analyze)
            compound_score = vs['compound']
            
            # Simple keyword adjustments for Forex context
            text_lower = text_to_analyze.lower()
            if "hawkish" in text_lower or "rate hike" in text_lower or "inflation rises" in text_lower:
                compound_score += 0.3
            if "dovish" in text_lower or "rate cut" in text_lower or "recession" in text_lower:
                compound_score -= 0.3
                
            # Clamp again
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
            "articles": analyzed_articles[:5], # Top 5
            "reasoning": summary_reasoning
        }

    async def _fetch_newsapi(self, currency: str) -> List[Dict[str, Any]]:
        """Fetch latest forex news from NewsAPI."""
        if not self.newsapi_key:
            return []

        keywords = self.currency_keywords.get(currency, [currency])
        query = " OR ".join([f'"{kw}"' for kw in keywords])
        formatted_query = quote_plus(f"({query}) AND (forex OR economy OR rates OR inflation OR bank)")

        # Last 24 hours
        from_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')

        url = f"https://newsapi.org/v2/everything?q={formatted_query}&from={from_date}&language=en&sortBy=publishedAt&apiKey={self.newsapi_key}"
        
        try:
            # Note: Using custom SSL context if needed, but normally httpx handles this.
            # Using timeout to prevent hanging.
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("articles", [])[:15]  # Limit to 15 most recent
                elif response.status_code == 426:
                    logger.warning("NewsAPI upgrade required (often happens if free plan is heavily restricted).")
                    return []
                else:
                    logger.warning(f"NewsAPI error: {response.status_code} - {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch news from NewsAPI: {e}")
            return []

# Singleton
sentiment_engine = SentimentEngine()
