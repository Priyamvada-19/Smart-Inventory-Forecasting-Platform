from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.ml import risk

router = APIRouter(prefix="/risk", tags=["Risk Prediction"])


@router.get("/summary", response_model=List[schemas.RiskSummary])
def risk_summary(db: Session = Depends(get_db), _: models.User = Depends(security.get_current_user)):
    products = db.query(models.Product).all()
    out = []
    for p in products:
        m = risk.compute_product_metrics(db, p)
        out.append(schemas.RiskSummary(
            product_id=p.id, sku=p.sku, name=p.name,
            days_of_supply=m["days_of_supply"], stockout_probability=m["stockout_probability"],
            overstock_probability=m["overstock_probability"], status=m["status"],
        ))
    return out


@router.get("/stockout", response_model=List[schemas.RiskSummary])
def stockout_risk(db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_user)):
    return [r for r in risk_summary(db, current_user) if r.status == "stockout-risk"]


@router.get("/overstock", response_model=List[schemas.RiskSummary])
def overstock_risk(db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_user)):
    return [r for r in risk_summary(db, current_user) if r.status in ("overstock", "dead-stock")]
