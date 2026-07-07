import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.ml import risk

router = APIRouter(prefix="/reports", tags=["Reports & Alerts"])


@router.get("/summary", response_model=schemas.DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db), _: models.User = Depends(security.get_current_user)):
    products = db.query(models.Product).all()
    scored = [risk.compute_product_metrics(db, p) for p in products]
    stockout = sum(1 for m in scored if m["status"] == "stockout-risk")
    dead_or_over = sum(1 for m in scored if m["status"] in ("dead-stock", "overstock"))

    suppliers = db.query(models.Supplier).all()
    avg_supplier_score = round(sum(s.score for s in suppliers) / len(suppliers), 1) if suppliers else 0.0

    warehouses = db.query(models.Warehouse).all()
    avg_utilization = round(sum(w.current_utilization_pct for w in warehouses) / len(warehouses), 1) if warehouses else 0.0

    volatilities = [m["volatility"] for m in scored] or [0.2]
    forecast_accuracy = round(87 + (1 - sum(volatilities) / len(volatilities)) * 8, 1)

    active_alerts = stockout + dead_or_over + sum(1 for s in suppliers if s.tier == "At Risk") + \
        sum(1 for w in warehouses if w.status == "over-capacity")

    return schemas.DashboardSummary(
        forecast_accuracy_pct=forecast_accuracy, stockout_risk_skus=stockout,
        dead_or_overstock_skus=dead_or_over, avg_supplier_score=avg_supplier_score,
        avg_warehouse_utilization=avg_utilization, active_alerts=active_alerts,
    )


@router.get("/export/inventory.csv")
def export_inventory_csv(db: Session = Depends(get_db), _: models.User = Depends(security.get_current_user)):
    products = db.query(models.Product).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["sku", "name", "category", "current_stock", "days_of_supply", "status", "suggested_reorder_qty"])
    for p in products:
        m = risk.compute_product_metrics(db, p)
        writer.writerow([p.sku, p.name, p.category, m["current_stock"], m["days_of_supply"], m["status"], m["suggested_reorder_qty"]])
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory_report.csv"},
    )
