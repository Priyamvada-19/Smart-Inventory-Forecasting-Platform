from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.ml import delay_prediction

router = APIRouter(prefix="/delivery", tags=["Delivery Delay Prediction"])


@router.get("/shipments", response_model=List[schemas.ShipmentOut])
def list_shipments(db: Session = Depends(get_db), _: models.User = Depends(security.get_current_user)):
    return db.query(models.Shipment).all()


@router.post("/shipments/{shipment_id}/refresh-prediction", response_model=schemas.ShipmentOut)
def refresh_prediction(
    shipment_id: int, db: Session = Depends(get_db),
    _: models.User = Depends(security.require_role(models.UserRole.admin, models.UserRole.manager, models.UserRole.analyst)),
):
    shipment = db.query(models.Shipment).get(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    supplier = shipment.supplier
    delay = delay_prediction.predict_delay(
        on_time_rate=supplier.on_time_rate, defect_rate=supplier.defect_rate,
        avg_lead_time_days=supplier.avg_lead_time_days, eta_days=shipment.eta_days,
    )
    shipment.predicted_delay_days = round(delay, 1)
    shipment.risk_level = delay_prediction.risk_level(delay)
    db.commit()
    db.refresh(shipment)
    return shipment
