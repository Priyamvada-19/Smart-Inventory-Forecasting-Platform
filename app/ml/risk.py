"""
Stockout / overstock risk scoring.

Business rules define what "risky" means (days-of-supply vs. lead time, sales trend),
but rather than hardcoding thresholds in the API we bootstrap a labeled training set
from those rules plus noise, and fit logistic regression classifiers on top. This gives
smooth probability estimates instead of a hard cutoff, and the model can be retrained
as real outcome data (actual stockouts/write-offs) becomes available.
"""
import random
from typing import Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from app.config import settings
from app import models
from sqlalchemy.orm import Session

MODEL_PATH = settings.artifacts_dir / "risk_models.joblib"

FEATURES = ["days_of_supply", "lead_time_days", "volatility", "sales_trend_pct"]


def _synthetic_training_set(n: int = 6000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    days_of_supply = rng.uniform(1, 180, n)
    lead_time_days = rng.uniform(3, 35, n)
    volatility = rng.uniform(0.02, 0.6, n)
    sales_trend_pct = rng.uniform(-40, 40, n)

    # rule-based bootstrap labels with a little noise so the boundary isn't a hard step
    stockout_label = (days_of_supply < lead_time_days * 1.15).astype(float)
    stockout_label = np.clip(stockout_label + rng.normal(0, 0.08, n), 0, 1).round()

    overstock_label = ((days_of_supply > 90) & (sales_trend_pct < 10)).astype(float)
    overstock_label = np.clip(overstock_label + rng.normal(0, 0.08, n), 0, 1).round()

    return pd.DataFrame({
        "days_of_supply": days_of_supply, "lead_time_days": lead_time_days,
        "volatility": volatility, "sales_trend_pct": sales_trend_pct,
        "stockout_label": stockout_label, "overstock_label": overstock_label,
    })


def train() -> dict:
    df = _synthetic_training_set()
    X = df[FEATURES]

    stockout_model = LogisticRegression(max_iter=1000).fit(X, df["stockout_label"])
    overstock_model = LogisticRegression(max_iter=1000).fit(X, df["overstock_label"])

    joblib.dump({"stockout": stockout_model, "overstock": overstock_model}, MODEL_PATH)
    return {"rows_trained": len(df)}


def _load():
    if not MODEL_PATH.exists():
        raise FileNotFoundError("Risk models not trained yet. Run app/ml/train_all.py")
    return joblib.load(MODEL_PATH)


def predict_risk(days_of_supply: float, lead_time_days: int, volatility: float, sales_trend_pct: float) -> Tuple[float, float]:
    bundle = _load()
    row = pd.DataFrame([{
        "days_of_supply": days_of_supply, "lead_time_days": lead_time_days,
        "volatility": volatility, "sales_trend_pct": sales_trend_pct,
    }])[FEATURES]
    stockout_p = float(bundle["stockout"].predict_proba(row)[0][1])
    overstock_p = float(bundle["overstock"].predict_proba(row)[0][1])
    return stockout_p, overstock_p


def compute_product_metrics(db: Session, product: models.Product) -> dict:
    """Pulls recent sales history + current stock to derive the features risk models need."""
    from datetime import datetime
    from dateutil.relativedelta import relativedelta

    cutoff = datetime.utcnow() - relativedelta(months=4)
    recent = (
        db.query(models.SalesRecord)
        .filter(models.SalesRecord.product_id == product.id, models.SalesRecord.period >= cutoff)
        .all()
    )
    monthly_totals = {}
    for r in recent:
        key = r.period.strftime("%Y-%m")
        monthly_totals[key] = monthly_totals.get(key, 0) + r.quantity_sold

    values = list(monthly_totals.values()) or [1]
    avg_monthly = sum(values) / len(values)
    daily_demand = max(avg_monthly / 30, 0.1)
    volatility = float(np.std(values) / avg_monthly) if avg_monthly else 0.0

    sorted_periods = sorted(monthly_totals.keys())
    if len(sorted_periods) >= 2:
        first, last = monthly_totals[sorted_periods[0]], monthly_totals[sorted_periods[-1]]
        sales_trend_pct = ((last - first) / first * 100) if first else 0.0
    else:
        sales_trend_pct = 0.0

    current_stock = sum(i.current_stock for i in product.inventory_items)
    days_of_supply = current_stock / daily_demand

    stockout_p, overstock_p = predict_risk(days_of_supply, product.lead_time_days, volatility, sales_trend_pct)

    if days_of_supply < product.lead_time_days * 1.1 or stockout_p > 0.6:
        status = "stockout-risk"
    elif days_of_supply > 120 and sales_trend_pct < -5:
        status = "dead-stock"
    elif days_of_supply > 90 or overstock_p > 0.6:
        status = "overstock"
    else:
        status = "healthy"

    reorder_qty = max(0, round(daily_demand * (product.lead_time_days + 30) + product.safety_stock - current_stock))

    return {
        "current_stock": current_stock, "avg_daily_demand": round(daily_demand, 2),
        "days_of_supply": round(days_of_supply, 1), "sales_trend_pct": round(sales_trend_pct, 1),
        "volatility": round(volatility, 3), "stockout_probability": round(stockout_p, 3),
        "overstock_probability": round(overstock_p, 3), "status": status,
        "suggested_reorder_qty": reorder_qty,
    }
