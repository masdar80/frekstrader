import os
try:
    import joblib
except ImportError:
    joblib = None
import pandas as pd
from typing import Dict, Any, Optional
from app.utils.logger import logger

class MLConfidenceCalibrator:
    """
    Uses a trained Random Forest model to adjust the confidence score
    of a trade based on the raw indicator features.
    """
    
    def __init__(self, model_path: str = "data/models/rf_calibrator.joblib"):
        self.model_path = model_path
        self.model = None
        self.features = []
        self._load_model()
        
    def _load_model(self):
        if not joblib:
            logger.warning("joblib/scikit-learn not installed. Operating in rule-based mode.")
            return
            
        if os.path.exists(self.model_path):
            try:
                data = joblib.load(self.model_path)
                self.model = data["model"]
                self.features = data["features"]
                logger.info(f"Loaded ML Calibrator model with {len(self.features)} features.")
            except Exception as e:
                logger.error(f"Failed to load ML Calibrator model: {e}")
        else:
            logger.info("No ML Calibrator model found. Operating in rule-based mode.")

    def calibrate(self, base_confidence: float, raw_indicators: Dict[str, Any], direction: str) -> float:
        """
        Predicts the probability of a win using the ML model.
        Returns the calibrated confidence.
        """
        if not self.model:
            return base_confidence
            
        try:
            # Flatten indicators to match training features
            row = {}
            if raw_indicators:
                for tf, inds in raw_indicators.items():
                    for ind, val in inds.items():
                        col_name = f"{ind}_{tf}"
                        row[col_name] = val
            
            # Create DataFrame with exactly the right columns, filling missing with 0
            df = pd.DataFrame([row])
            for f in self.features:
                if f not in df.columns:
                    df[f] = 0.0
            
            X = df[self.features]
            
            # Predict probability of class 1 (WIN)
            prob_win = self.model.predict_proba(X)[0][1]
            
            # Blending: 60% rule-based, 40% ML-based
            blended = (base_confidence * 0.6) + (prob_win * 0.4)
            return round(blended, 3)
            
        except Exception as e:
            logger.error(f"ML Calibration failed: {e}")
            return base_confidence

ml_calibrator = MLConfidenceCalibrator()
