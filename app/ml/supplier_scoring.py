"""
Supplier intelligence.

The composite score is a transparent weighted formula (easy to explain to a supply
chain manager). Tiers (Preferred / Standard / At Risk) are assigned by KMeans
clustering across the underlying metrics rather than a fixed score cutoff, so the
boundary adapts to how the whole supplier base is actually performing this quarter.
"""
from typing import List

import joblib
import numpy as np
from sklearn.cluster import KMeans

from app.config import settings
from app import models

MODEL_PATH = settings.artifacts_dir / "supplier_cluster_model.joblib"

FEATURES = ["on_time_rate", "quality_score", "responsiveness", "fill_rate"]


def composite_score(on_time_rate: float, defect_rate: float, responsiveness: float, fill_rate: float) -> float:
    quality_score = max(0.0, 100 - defect_rate * 8)
    return round(on_time_rate * 0.35 + quality_score * 0.25 + responsiveness * 0.20 + fill_rate * 0.20, 1)


def train(suppliers: List[models.Supplier]) -> dict:
    X = np.array([
        [s.on_time_rate, max(0.0, 100 - s.defect_rate * 8), s.responsiveness, s.fill_rate]
        for s in suppliers
    ])
    k = min(3, len(suppliers))
    model = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
    joblib.dump(model, MODEL_PATH)
    return {"suppliers_clustered": len(suppliers), "clusters": k}


def assign_tiers(db_suppliers: List[models.Supplier]) -> None:
    """Recomputes score for each supplier and assigns a tier via the trained cluster model."""
    if not MODEL_PATH.exists():
        train(db_suppliers)
    model = joblib.load(MODEL_PATH)

    X = np.array([
        [s.on_time_rate, max(0.0, 100 - s.defect_rate * 8), s.responsiveness, s.fill_rate]
        for s in db_suppliers
    ])
    scores = [composite_score(s.on_time_rate, s.defect_rate, s.responsiveness, s.fill_rate) for s in db_suppliers]
    clusters = model.predict(X)

    # map each cluster id to a tier name based on that cluster's average score
    cluster_avg_score = {}
    for c, sc in zip(clusters, scores):
        cluster_avg_score.setdefault(c, []).append(sc)
    ranked_clusters = sorted(cluster_avg_score, key=lambda c: -np.mean(cluster_avg_score[c]))
    tier_names = ["Preferred", "Standard", "At Risk"]
    cluster_to_tier = {c: tier_names[min(i, len(tier_names) - 1)] for i, c in enumerate(ranked_clusters)}

    for supplier, score, cluster in zip(db_suppliers, scores, clusters):
        supplier.score = score
        supplier.tier = cluster_to_tier[cluster]
