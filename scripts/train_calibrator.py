import asyncio
import os
import sys
import joblib
import pandas as pd
from sqlalchemy import select

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.database import async_session
from app.db.models import FeatureSnapshot
from app.utils.logger import logger

async def train():
    print("--- ML Calibrator Training ---")
    async with async_session() as db:
        result = await db.execute(select(FeatureSnapshot).where(FeatureSnapshot.outcome != None))
        snapshots = result.scalars().all()
        
        if len(snapshots) < 50:
            print(f"Need at least 50 closed trades to train the calibrator. Found: {len(snapshots)}")
            return
            
        print(f"Loaded {len(snapshots)} training samples.")
        
        rows = []
        for s in snapshots:
            row = {
                "outcome": s.outcome,
            }
            if s.indicators_json:
                for tf, inds in s.indicators_json.items():
                    for ind, val in inds.items():
                        col_name = f"{ind}_{tf}"
                        row[col_name] = val
            rows.append(row)
            
        df = pd.DataFrame(rows)
        df["win"] = (df["outcome"] == "WIN").astype(int)
        
        numeric_cols = df.select_dtypes(include=['float64', 'int64', 'int32']).columns
        exclude = ["win", "outcome"]
        feature_cols = [c for c in numeric_cols if c not in exclude]
        
        ml_df = df.dropna(subset=feature_cols + ["win"])
        if len(ml_df) < 50:
            print(f"After dropping NaNs, only {len(ml_df)} samples remain. Cannot train.")
            return
            
        X = ml_df[feature_cols]
        y = ml_df["win"]
        
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import cross_val_score
            
            print(f"Training Random Forest on {len(feature_cols)} features...")
            rf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
            
            # Simple CV to see if model is learning anything
            scores = cross_val_score(rf, X, y, cv=5, scoring='accuracy')
            print(f"Cross-Validation Accuracy: {scores.mean():.3f} (+/- {scores.std() * 2:.3f})")
            
            rf.fit(X, y)
            
            model_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'models')
            os.makedirs(model_dir, exist_ok=True)
            model_path = os.path.join(model_dir, 'rf_calibrator.joblib')
            
            joblib.dump({"model": rf, "features": feature_cols}, model_path)
            print(f"Model saved to {model_path}")
            
        except ImportError:
            print("Please install scikit-learn to train the model: pip install scikit-learn joblib")

if __name__ == "__main__":
    asyncio.run(train())
