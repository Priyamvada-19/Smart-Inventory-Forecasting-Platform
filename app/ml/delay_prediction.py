"""
Delivery delay prediction.

Trained on synthetic shipment records generated with the same distribution used to
seed the shipments table, so the model recovers the underlying relationship between
supplier reliability and delay risk. In production this would train directly on
historical shipment outcomes (planned ETA vs. actual delivery date).
"""
import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from app.config import settings

MODEL_PATH = settings.artifacts_dir / "delay_model.joblib"
FEATURES = ["on_time_rate", "defect_rate", "avg_lead_time_days", "eta_days", "season_factor"]


def _synthetic_shipments(n: int = 5000, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    on_time_rate = rng.uniform(60, 99, n)
    defect_rate = rng.uniform(0.2, 6.0, n)
    avg_lead_time_days = rng.uniform(4, 35, n)
    eta_days = rng.uniform(2, 15, n)
    season_factor = rng.uniform(0.8, 1.4, n)  # e.g. peak season congestion multiplier

    base_risk = (100 - on_time_rate) / 100
    delay = (
        base_risk * 7
        + defect_rate * 0.3
        + (avg_lead_time_days / 35) * 2
        + (season_factor - 1) * 5
        + rng.normal(0, 1.0, n)
    )
    delay = np.clip(delay, 0, None)

    return pd.DataFrame({
        "on_time_rate": on_time_rate, "defect_rate": defect_rate,
        "avg_lead_time_days": avg_lead_time_days, "eta_days": eta_days,
        "season_factor": season_factor, "predicted_delay_days": delay,
    })


def train() -> dict:
    df = _synthetic_shipments()
    model = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.07, random_state=42)
    model.fit(df[FEATURES], df["predicted_delay_days"])
    joblib.dump(model, MODEL_PATH)
    return {"rows_trained": len(df)}


def predict_delay(on_time_rate: float, defect_rate: float, avg_lead_time_days: float,
                   eta_days: float, season_factor: float = 1.0) -> float:
    if not MODEL_PATH.exists():
        raise FileNotFoundError("Delay model not trained yet. Run app/ml/train_all.py")
    model = joblib.load(MODEL_PATH)
    row = pd.DataFrame([{
        "on_time_rate": on_time_rate, "defect_rate": defect_rate,
        "avg_lead_time_days": avg_lead_time_days, "eta_days": eta_days,
        "season_factor": season_factor,
    }])[FEATURES]
    return max(0.0, float(model.predict(row)[0]))


def risk_level(delay_days: float) -> str:
    if delay_days >= 5:
        return "high"
    if delay_days >= 2:
        return "medium"
    return "low"
