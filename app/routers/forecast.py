from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.ml import forecasting

router = APIRouter(prefix="/forecast", tags=["Demand Forecasting"])


@router.get("/{product_id}", response_model=schemas.ForecastResponse)
def get_forecast(
    product_id: int, horizon: int = 3,
    db: Session = Depends(get_db), _: models.User = Depends(security.get_current_user),
):
    product = db.query(models.Product).get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        points = forecasting.predict(db, product_id, horizon=horizon)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    history_avg = forecasting.get_history_avg_monthly(db, product_id)
    history = forecasting.get_history_series(db, product_id)
    return schemas.ForecastResponse(
        product_id=product.id, sku=product.sku, name=product.name,
        history_avg_monthly=round(history_avg, 1),
        history=[schemas.HistoryPoint(**h) for h in history],
        forecast=[schemas.ForecastPoint(**p) for p in points],
    )
