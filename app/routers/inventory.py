from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.ml import risk

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("/", response_model=List[schemas.InventoryOut])
def list_inventory(db: Session = Depends(get_db), _: models.User = Depends(security.get_current_user)):
    return db.query(models.Inventory).all()


@router.post("/", response_model=schemas.InventoryOut, status_code=201)
def create_inventory(
    payload: schemas.InventoryCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(security.require_role(models.UserRole.admin, models.UserRole.manager)),
):
    if not db.query(models.Product).get(payload.product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    if not db.query(models.Warehouse).get(payload.warehouse_id):
        raise HTTPException(status_code=404, detail="Warehouse not found")
    item = models.Inventory(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{inventory_id}", response_model=schemas.InventoryOut)
def update_stock(
    inventory_id: int, payload: schemas.InventoryUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(security.require_role(models.UserRole.admin, models.UserRole.manager)),
):
    item = db.query(models.Inventory).get(inventory_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    item.current_stock = payload.current_stock
    db.commit()
    db.refresh(item)
    return item


@router.get("/reorder-recommendations", response_model=List[schemas.ReorderRecommendation])
def reorder_recommendations(db: Session = Depends(get_db), _: models.User = Depends(security.get_current_user)):
    """
    Runs the stockout/overstock risk model against every product's current
    position and returns a prioritized reorder list.
    """
    products = db.query(models.Product).all()
    results = []
    for p in products:
        metrics = risk.compute_product_metrics(db, p)
        results.append(schemas.ReorderRecommendation(
            product_id=p.id, sku=p.sku, name=p.name,
            current_stock=metrics["current_stock"], avg_daily_demand=metrics["avg_daily_demand"],
            days_of_supply=metrics["days_of_supply"], lead_time_days=p.lead_time_days,
            reorder_point=p.reorder_point, suggested_reorder_qty=metrics["suggested_reorder_qty"],
            status=metrics["status"],
        ))
    # surface most urgent first
    severity_rank = {"stockout-risk": 0, "dead-stock": 1, "overstock": 2, "healthy": 3}
    results.sort(key=lambda r: (severity_rank[r.status], r.days_of_supply))
    return results
