import asyncio
import os
import sys
import pandas as pd
from sqlalchemy import select

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.database import async_session
from app.db.models import FeatureSnapshot

async def run_analysis():
    print("--- Indicator Importance Analysis ---")
    async with async_session() as db:
        result = await db.execute(select(FeatureSnapshot).where(FeatureSnapshot.outcome != None))
        snapshots = result.scalars().all()
        
        if not snapshots:
            print("No feature snapshots with outcomes found. Wait for the bot to take some trades.")
            return

        print(f"Loaded {len(snapshots)} feature snapshots.")

        rows = []
        for s in snapshots:
            row = {
                "id": s.id,
                "symbol": s.symbol,
                "outcome": s.outcome,
                "profit_pips": s.profit_pips or 0.0,
                "regime": s.market_regime,
            }
            # Flatten indicators_json
            if s.indicators_json:
                for tf, inds in s.indicators_json.items():
                    for ind, val in inds.items():
                        col_name = f"{ind}_{tf}"
                        row[col_name] = val
            rows.append(row)
            
        df = pd.DataFrame(rows)
        df["win"] = (df["outcome"] == "WIN").astype(int)
        
        numeric_cols = df.select_dtypes(include=['float64', 'int64', 'int32']).columns
        exclude = ["id", "profit_pips", "win"]
        feature_cols = [c for c in numeric_cols if c not in exclude]
        
        correlations = []
        for col in feature_cols:
            if df[col].nunique() > 1:
                corr = df[col].corr(df["profit_pips"])
                correlations.append({"Feature": col, "Correlation": corr})
                
        corr_df = pd.DataFrame(correlations).sort_values("Correlation", key=abs, ascending=False)
        print("\n--- Correlation with Profit (Pips) ---")
        if not corr_df.empty:
            print(corr_df.dropna().head(20).to_string(index=False))
        else:
            print("No valid numeric features found.")

        try:
            from sklearn.ensemble import RandomForestClassifier
            
            ml_df = df.dropna(subset=feature_cols + ["win"])
            if len(ml_df) > 50:
                X = ml_df[feature_cols]
                y = ml_df["win"]
                
                rf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
                rf.fit(X, y)
                
                importances = pd.DataFrame({
                    "Feature": feature_cols,
                    "Importance": rf.feature_importances_
                }).sort_values("Importance", ascending=False)
                
                print("\n--- Random Forest Feature Importance ---")
                print(importances.head(20).to_string(index=False))
            else:
                print(f"\nNeed at least 50 complete records for Random Forest analysis. Only have {len(ml_df)}.")
                
        except ImportError:
            print("\nInstall 'scikit-learn' for advanced feature importance (Random Forest).")

if __name__ == "__main__":
    asyncio.run(run_analysis())
