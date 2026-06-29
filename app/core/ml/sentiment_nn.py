try:
    from transformers import pipeline
except ImportError:
    pipeline = None

from typing import List, Dict, Any
from app.utils.logger import logger

class NeuralSentimentClassifier:
    """
    Uses a local HuggingFace NLP model (e.g. FinBERT) to classify
    financial news headlines into positive, negative, or neutral sentiment.
    Runs locally on CPU.
    """
    def __init__(self, model_name="ProsusAI/finbert"):
        self.model_name = model_name
        self.classifier = None
        self.is_loaded = False
        
    def load_model(self):
        if not pipeline:
            logger.error("transformers library is not installed. Run: pip install transformers torch")
            return
            
        try:
            logger.info(f"Loading local NLP Sentiment Model: {self.model_name}...")
            self.classifier = pipeline("sentiment-analysis", model=self.model_name, device=-1)
            self.is_loaded = True
            logger.info("✅ NLP Sentiment Model Loaded.")
        except Exception as e:
            logger.error(f"Failed to load NLP Sentiment Model: {e}")
            self.is_loaded = False
            
    def analyze_headlines(self, headlines: List[str]) -> Dict[str, float]:
        """
        Analyzes a list of text headlines and returns a unified sentiment score.
        Score range: 1.0 (Very Positive) to -1.0 (Very Negative)
        """
        if not self.is_loaded:
            logger.warning("Sentiment model not loaded. Returning neutral.")
            return {"score": 0.0, "confidence": 0.0}
            
        if not headlines:
            return {"score": 0.0, "confidence": 0.0}
            
        try:
            results = self.classifier(headlines)
            
            total_score = 0.0
            total_conf = 0.0
            
            for res in results:
                label = res["label"].lower()
                conf = res["score"]
                
                if label == "positive":
                    total_score += conf
                elif label == "negative":
                    total_score -= conf
                    
                total_conf += conf
                
            avg_score = total_score / len(headlines)
            avg_conf = total_conf / len(headlines)
            
            return {
                "score": round(avg_score, 3),
                "confidence": round(avg_conf, 3)
            }
        except Exception as e:
            logger.error(f"NLP classification failed: {e}")
            return {"score": 0.0, "confidence": 0.0}

neural_sentiment = NeuralSentimentClassifier()
