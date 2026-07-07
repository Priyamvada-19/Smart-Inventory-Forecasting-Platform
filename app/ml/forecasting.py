"""
Demand forecasting model.

Trains a single global XGBoost regressor over all products' monthly sales history
(rather than one model per SKU) so the model can share seasonal/category patterns
across products -- this generalizes better with limited history per SKU, which is
the realistic constraint most retail/e-commerce teams actually face.

Features: product & category (label-encoded), calendar seasonality (sin/cos of month),
lag-1/2/3 demand, 3-month rolling mean, and exogenous signals (promotion flag,
competitor price ratio, weather index).
"""
import math
from pathlib import Path
from typing import List

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sqlalchemy.orm import Session
from xgboost import XGBRegressor

from app import models
from app.config import settings

MODEL_PATH = settings.artifacts_dir / "demand_forecast_model.joblib"
ENCODERS_PATH = settings.artifacts_dir / "demand_forecast_encoders.joblib"


def _load_monthly_frame(db: Session) -> pd.DataFrame:
    rows = (
        db.query(
            models.SalesRecord.product_id,
            models.Product.sku,
            models.Product.category,
            models.SalesRecord.period,
            models.SalesRecord.quantity_sold,
            models.SalesRecord.promotion_active,
            models.SalesRecord.competitor_price_ratio,
            models.SalesRecord.weather_index,
        )
        .join(models.Product, models.Product.id == models.SalesRecord.product_id)
        .all()
    )
    df = pd.DataFrame(rows, columns=[
        "product_id", "sku", "category", "period", "quantity_sold",
        "promotion_active", "competitor_price_ratio", "weather_index",
    ])
    # collapse regions -> product-level monthly total (what we actually forecast against)
    agg = (
        df.groupby(["product_id", "sku", "category", "period"])
        .agg(
            quantity_sold=("quantity_sold", "sum"),
            promotion_active=("promotion_active", "mean"),
            competitor_price_ratio=("competitor_price_ratio", "mean"),
            weather_index=("weather_index", "mean"),
        )
        .reset_index()
        .sort_values(["product_id", "period"])
    )
    return agg


def _add_features(df: pd.DataFrame, cat_encoder: LabelEncoder, prod_encoder: LabelEncoder) -> pd.DataFrame:
    df = df.copy()
    df["month"] = pd.to_datetime(df["period"]).dt.month
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["category_enc"] = cat_encoder.transform(df["category"])
    df["product_enc"] = prod_encoder.transform(df["product_id"])

    df["lag_1"] = df.groupby("product_id")["quantity_sold"].shift(1)
    df["lag_2"] = df.groupby("product_id")["quantity_sold"].shift(2)
    df["lag_3"] = df.groupby("product_id")["quantity_sold"].shift(3)
    df["rolling_mean_3"] = df.groupby("product_id")["quantity_sold"].shift(1).rolling(3).mean()
    return df


FEATURE_COLS = [
    "product_enc", "category_enc", "month_sin", "month_cos",
    "lag_1", "lag_2", "lag_3", "rolling_mean_3",
    "promotion_active", "competitor_price_ratio", "weather_index",
]


def train(db: Session) -> dict:
    raw = _load_monthly_frame(db)
    cat_encoder = LabelEncoder().fit(raw["category"])
    prod_encoder = LabelEncoder().fit(raw["product_id"])

    feat = _add_features(raw, cat_encoder, prod_encoder).dropna(subset=FEATURE_COLS)

    X = feat[FEATURE_COLS]
    y = feat["quantity_sold"]

    model = XGBRegressor(
        n_estimators=250, max_depth=4, learning_rate=0.06,
        subsample=0.85, colsample_bytree=0.85, random_state=42,
    )
    model.fit(X, y)

    residuals = y - model.predict(X)
    residual_std = float(np.std(residuals))

    joblib.dump({"model": model, "residual_std": residual_std}, MODEL_PATH)
    joblib.dump({"category": cat_encoder, "product": prod_encoder}, ENCODERS_PATH)

    return {"rows_trained": len(feat), "residual_std": residual_std}


def _load():
    if not MODEL_PATH.exists():
        raise FileNotFoundError("Demand forecasting model not trained yet. Run app/ml/train_all.py")
    bundle = joblib.load(MODEL_PATH)
    encoders = joblib.load(ENCODERS_PATH)
    return bundle["model"], bundle["residual_std"], encoders


def get_history_avg_monthly(db: Session, product_id: int) -> float:
    raw = _load_monthly_frame(db)
    history = raw[raw["product_id"] == product_id]
    if history.empty:
        return 0.0
    return float(history["quantity_sold"].mean())


def get_history_series(db: Session, product_id: int) -> List[dict]:
    """Actual monthly units sold, for charting alongside the forecast."""
    raw = _load_monthly_frame(db)
    history = raw[raw["product_id"] == product_id].sort_values("period")
    return [
        {"period": pd.to_datetime(row.period).strftime("%Y-%m"), "actual_units": float(row.quantity_sold)}
        for row in history.itertuples()
    ]


def predict(db: Session, product_id: int, horizon: int = 3) -> List[dict]:
    model, residual_std, encoders = _load()
    raw = _load_monthly_frame(db)
    history = raw[raw["product_id"] == product_id].sort_values("period")
    if history.empty:
        raise ValueError(f"No sales history for product_id={product_id}")

    cat_encoder, prod_encoder = encoders["category"], encoders["product"]
    series = history["quantity_sold"].tolist()
    last_period = pd.to_datetime(history["period"].iloc[-1])
    category = history["category"].iloc[0]
    avg_promo = float(history["promotion_active"].mean())
    avg_competitor = float(history["competitor_price_ratio"].mean())
    avg_weather = float(history["weather_index"].mean())

    forecasts = []
    working_series = list(series)
    for step in range(1, horizon + 1):
        period = last_period + pd.DateOffset(months=step)
        month = period.month
        row = {
            "product_enc": prod_encoder.transform([product_id])[0],
            "category_enc": cat_encoder.transform([category])[0],
            "month_sin": math.sin(2 * math.pi * month / 12),
            "month_cos": math.cos(2 * math.pi * month / 12),
            "lag_1": working_series[-1],
            "lag_2": working_series[-2] if len(working_series) >= 2 else working_series[-1],
            "lag_3": working_series[-3] if len(working_series) >= 3 else working_series[-1],
            "rolling_mean_3": float(np.mean(working_series[-3:])),
            "promotion_active": avg_promo,
            "competitor_price_ratio": avg_competitor,
            "weather_index": avg_weather,
        }
        X_pred = pd.DataFrame([row])[FEATURE_COLS]
        pred = max(0.0, float(model.predict(X_pred)[0]))
        working_series.append(pred)
        forecasts.append({
            "period": period.strftime("%Y-%m"),
            "predicted_units": round(pred, 1),
            "lower_bound": round(max(0.0, pred - 1.28 * residual_std), 1),
            "upper_bound": round(pred + 1.28 * residual_std, 1),
        })
    return forecasts
