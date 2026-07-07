from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db

router = APIRouter(prefix="/warehouses", tags=["Warehouses"])


@router.get("/", response_model=List[schemas.WarehouseOut])
def list_warehouses(db: Session = Depends(get_db), _: models.User = Depends(security.get_current_user)):
    return db.query(models.Warehouse).all()


@router.get("/{warehouse_id}", response_model=schemas.WarehouseOut)
def get_warehouse(warehouse_id: int, db: Session = Depends(get_db), _: models.User = Depends(security.get_current_user)):
    w = db.query(models.Warehouse).get(warehouse_id)
    if not w:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return w


@router.get("/optimization/rebalance-suggestions")
def rebalance_suggestions(db: Session = Depends(get_db), _: models.User = Depends(security.get_current_user)):
    """Pairs over-capacity warehouses with under-utilized ones as simple rebalancing suggestions."""
    warehouses = db.query(models.Warehouse).all()
    over = sorted([w for w in warehouses if w.status == "over-capacity"], key=lambda w: -w.current_utilization_pct)
    under = sorted([w for w in warehouses if w.status == "under-utilized"], key=lambda w: w.current_utilization_pct)

    suggestions = []
    for o, u in zip(over, under):
        suggestions.append({
            "from_warehouse": o.name, "from_utilization_pct": o.current_utilization_pct,
            "to_warehouse": u.name, "to_utilization_pct": u.current_utilization_pct,
        })
    return suggestions
