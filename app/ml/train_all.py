"""
Trains every model in the platform against the current database contents and
saves artifacts to app/artifacts/. Run this after seeding, and re-run periodically
(e.g. nightly) as new sales/shipment data accumulates.

Usage:
    python -m app.ml.train_all
"""
from app.database import SessionLocal
from app import models
from app.ml import forecasting, risk, supplier_scoring, delay_prediction


def main():
    db = SessionLocal()
    try:
        print("Training demand forecasting model...")
        print(" ", forecasting.train(db))

        print("Training stockout/overstock risk classifiers...")
        print(" ", risk.train())

        print("Training delivery delay regressor...")
        print(" ", delay_prediction.train())

        print("Clustering suppliers into performance tiers...")
        suppliers = db.query(models.Supplier).all()
        print(" ", supplier_scoring.train(suppliers))
        supplier_scoring.assign_tiers(suppliers)
        db.commit()

        print("All models trained and saved to artifacts/.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
