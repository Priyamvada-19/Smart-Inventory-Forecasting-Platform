from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.ml import risk

router = APIRouter(prefix="/recommendations", tags=["AI Recommendations"])


@router.get("/", response_model=List[schemas.Recommendation])
def get_recommendations(db: Session = Depends(get_db), _: models.User = Depends(security.get_current_user)):
    """
    Combines risk scoring, supplier tiers, and warehouse utilization into a
    single prioritized list of proactive actions -- the same logic the
    dashboard's "AI Recommendations" tab renders.
    """
    recs: List[schemas.Recommendation] = []

    products = db.query(models.Product).all()
    scored = [(p, risk.compute_product_metrics(db, p)) for p in products]

    stockout = sorted(
        [(p, m) for p, m in scored if m["status"] == "stockout-risk"],
        key=lambda pm: pm[1]["days_of_supply"],
    )
    if stockout:
        p, m = stockout[0]
        recs.append(schemas.Recommendation(
            category="inventory", severity="critical",
            title=f"Raise a purchase order for {p.name} today",
            detail=f"{m['days_of_supply']}d of supply left against a {p.lead_time_days}d lead time. "
                   f"Ordering {m['suggested_reorder_qty']} units now avoids a stockout.",
            impact=f"Protects roughly ₹{round(m['avg_daily_demand'] * 30 * p.unit_price):,} in monthly revenue",
        ))

    dead = sorted(
        [(p, m) for p, m in scored if m["status"] == "dead-stock"],
        key=lambda pm: -pm[1]["days_of_supply"],
    )
    if dead:
        p, m = dead[0]
        stock_value = round(m["current_stock"] * p.unit_cost)
        recs.append(schemas.Recommendation(
            category="inventory", severity="warning",
            title=f"Markdown {p.name} to clear dead stock",
            detail=f"{m['days_of_supply']}d of supply with sales down {abs(m['sales_trend_pct'])}% recently.",
            impact=f"Frees up roughly ₹{stock_value:,} in working capital",
        ))

    suppliers = db.query(models.Supplier).order_by(models.Supplier.score).all()
    if suppliers and suppliers[0].tier == "At Risk":
        worst, best = suppliers[0], suppliers[-1]
        recs.append(schemas.Recommendation(
            category="supplier", severity="warning",
            title=f"Diversify sourcing away from {worst.name}",
            detail=f"Score of {worst.score}/100 with {worst.on_time_rate}% on-time delivery, "
                   f"vs. {best.name} at {best.score}/100.",
            impact="Reduces delivery-delay exposure",
        ))

    warehouses = db.query(models.Warehouse).all()
    over = next((w for w in warehouses if w.status == "over-capacity"), None)
    under = next((w for w in warehouses if w.status == "under-utilized"), None)
    if over and under:
        recs.append(schemas.Recommendation(
            category="warehouse", severity="warning",
            title=f"Shift volume from {over.name} to {under.name}",
            detail=f"{over.name} is at {over.current_utilization_pct}% capacity while "
                   f"{under.name} sits at {under.current_utilization_pct}%.",
            impact="Improves fulfillment speed network-wide",
        ))

    best_region = db.query(models.Region).order_by(models.Region.growth_rate_pct.desc()).first()
    if best_region:
        recs.append(schemas.Recommendation(
            category="regional", severity="info",
            title=f"Increase allocation to the {best_region.name} region",
            detail=f"Demand is growing {best_region.growth_rate_pct}% with a demand index of {best_region.demand_index}.",
            impact="Captures upside before competitors reallocate",
        ))

    return recs
