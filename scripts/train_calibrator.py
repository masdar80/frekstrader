import asyncio
import os
import sys
import joblib
import pandas as pd
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.database import async_session
from app.db.models import FeatureSnapshot
from sqlalchemy import select

TIMEFRAMES = ['15m', '1h', '4h', '1d']
INDICATORS = ['RSI', 'MACD', 'EMA_CROSS', 'EMA200_TREND', 'BBANDS', 'ATR', 'STOCH', 'ADX']


async def train():
    print("--- ML Calibrator Training v2 (Full Multi-Timeframe) ---")
    async with async_session() as db:
        result = await db.execute(
            select(FeatureSnapshot).where(FeatureSnapshot.outcome.in_(["WIN", "LOSS"]))
        )
        snapshots = result.scalars().all()

    if len(snapshots) < 50:
        print(f"Need at least 50 closed trades. Found: {len(snapshots)}")
        return

    print(f"Loaded {len(snapshots)} training samples.")

    rows = []
    skipped = 0
    for s in snapshots:
        row = {
            "win": 1 if s.outcome == "WIN" else 0,
            "atr_1h":     s.atr_1h,
            "atr_4h":     s.atr_4h,
            "spread_pips": s.spread_pips,
            "hour_of_day": s.hour_of_day,
            "day_of_week": s.day_of_week,
        }

        if not s.indicators_json:
            skipped += 1
            continue

        try:
            inds = s.indicators_json if isinstance(s.indicators_json, dict) else json.loads(s.indicators_json)

            # Detect format
            top_keys = set(inds.keys())
            is_timeframe_format = bool(top_keys & {'15m', '1h', '4h', '1d'})

            if is_timeframe_format:
                # Correct format: {timeframe: {indicator: value}}
                for tf in TIMEFRAMES:
                    tf_data = inds.get(tf, {})
                    for ind in INDICATORS:
                        val = tf_data.get(ind)
                        row[f"{ind}_{tf}"] = float(val) if val is not None else None
            else:
                # Old format: {indicator: {indicator: value}} - extract single value per indicator
                for ind in INDICATORS:
                    ind_data = inds.get(ind, {})
                    if isinstance(ind_data, dict):
                        vals = [v for v in ind_data.values() if isinstance(v, (int, float))]
                        row[f"{ind}_avg"] = sum(vals) / len(vals) if vals else None
                    elif isinstance(ind_data, (int, float)):
                        row[f"{ind}_avg"] = float(ind_data)
                    else:
                        row[f"{ind}_avg"] = None

        except Exception as e:
            skipped += 1
            continue

        rows.append(row)

    print(f"Processed {len(rows)} samples ({skipped} skipped).")

    df = pd.DataFrame(rows)
    feature_cols = [c for c in df.columns if c != "win"]

    # Fill NaN with column median
    for col in feature_cols:
        median_val = df[col].median()
        df[col] = df[col].fillna(median_val)

    # Drop columns that are still all NaN
    df = df.dropna(axis=1, how='all')
    feature_cols = [c for c in df.columns if c != "win"]

    print(f"\nFeatures used: {len(feature_cols)}")
    print(f"Win rate in training data: {df['win'].mean():.1%}")
    print(f"Class balance: {df['win'].sum()} wins, {(df['win']==0).sum()} losses")

    X = df[feature_cols]
    y = df["win"]

    try:
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
        from sklearn.model_selection import cross_val_score, StratifiedKFold

        print(f"\nTraining on {len(X)} samples with {len(feature_cols)} features...")

        rf = RandomForestClassifier(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=10,
            random_state=42,
            class_weight='balanced',
            n_jobs=-1
        )

        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        scores = cross_val_score(rf, X, y, cv=cv, scoring='roc_auc')
        print(f"Cross-Validation ROC-AUC: {scores.mean():.3f} (+/- {scores.std() * 2:.3f})")
        print(f"Per-fold scores: {[f'{s:.3f}' for s in scores]}")

        rf.fit(X, y)

        # Feature importance
        importance = sorted(zip(feature_cols, rf.feature_importances_), key=lambda x: -x[1])
        print("\nTop 15 Feature Importances:")
        for feat, imp in importance[:15]:
            bar = '#' * int(imp * 200)
            print(f"  {feat:25s}: {imp:.4f} {bar}")

        model_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'models')
        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, 'rf_calibrator.joblib')

        joblib.dump({"model": rf, "features": feature_cols}, model_path)
        print(f"\nModel saved to {model_path}")
        print("\nDone! The ML Calibrator is now active.")

    except ImportError as e:
        print(f"Missing dependency: {e}")


if __name__ == "__main__":
    asyncio.run(train())
