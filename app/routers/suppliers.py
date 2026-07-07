from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.ml import supplier_scoring

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.get("/", response_model=List[schemas.SupplierOut])
def list_suppliers(db: Session = Depends(get_db), _: models.User = Depends(security.get_current_user)):
    return db.query(models.Supplier).all()


@router.get("/ranking", response_model=List[schemas.SupplierOut])
def supplier_ranking(db: Session = Depends(get_db), _: models.User = Depends(security.get_current_user)):
    """Suppliers ranked best to worst by composite score."""
    return db.query(models.Supplier).order_by(models.Supplier.score.desc()).all()


@router.post("/", response_model=schemas.SupplierOut, status_code=201)
def create_supplier(
    payload: schemas.SupplierCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(security.require_role(models.UserRole.admin, models.UserRole.manager)),
):
    score = supplier_scoring.composite_score(
        payload.on_time_rate, payload.defect_rate, payload.responsiveness, payload.fill_rate
    )
    tier = "Preferred" if score >= 80 else "Standard" if score >= 65 else "At Risk"
    supplier = models.Supplier(**payload.model_dump(), score=score, tier=tier)
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.post("/recompute-tiers", status_code=200)
def recompute_tiers(
    db: Session = Depends(get_db),
    _: models.User = Depends(security.require_role(models.UserRole.admin, models.UserRole.manager)),
):
    """Re-runs the KMeans tier clustering across the current supplier base."""
    suppliers = db.query(models.Supplier).all()
    if not suppliers:
        raise HTTPException(status_code=400, detail="No suppliers to cluster")
    supplier_scoring.assign_tiers(suppliers)
    db.commit()
    return {"updated": len(suppliers)}
