from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db

router = APIRouter(prefix="/regions", tags=["Regional & Seasonal Demand"])


@router.get("/", response_model=List[schemas.RegionOut])
def list_regions(db: Session = Depends(get_db), _: models.User = Depends(security.get_current_user)):
    return db.query(models.Region).all()


@router.get("/{region_id}/monthly-demand", response_model=List[schemas.RegionMonthlyPoint])
def region_monthly_demand(region_id: int, db: Session = Depends(get_db), _: models.User = Depends(security.get_current_user)):
    """Total units sold across all products in this region, by month -- powers the seasonal demand chart."""
    region = db.query(models.Region).get(region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    rows = db.query(models.SalesRecord).filter(models.SalesRecord.region_id == region_id).all()
    monthly = {}
    for r in rows:
        key = r.period.strftime("%Y-%m")
        monthly[key] = monthly.get(key, 0) + r.quantity_sold

    return [
        schemas.RegionMonthlyPoint(period=k, quantity=v)
        for k, v in sorted(monthly.items())
    ]
