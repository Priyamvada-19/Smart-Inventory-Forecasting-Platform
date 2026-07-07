"""
Run once (or on container startup) to bring the platform to a fully working state:
  1. Create all tables
  2. Seed synthetic products/suppliers/warehouses/regions/sales/shipments
  3. Create a default admin user
  4. Train every ML model against the seeded data

Usage:
    python init_db.py
"""
from app.database import Base, engine, SessionLocal
from app import models, security
from app.data_gen import seed_database
from app.ml import train_all


def create_default_admin(db):
    if db.query(models.User).filter(models.User.username == "admin").first():
        return
    admin = models.User(
        username="admin",
        email="admin@chainmind.local",
        hashed_password=security.hash_password("ChangeMe123!"),
        role=models.UserRole.admin,
    )
    db.add(admin)
    db.commit()
    print("Created default admin user -> username: admin / password: ChangeMe123!  (change this immediately)")


def main():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("Seeding synthetic data (skips if already seeded)...")
        seed_database(db)

        print("Ensuring a default admin user exists...")
        create_default_admin(db)
    finally:
        db.close()

    print("Training ML models...")
    train_all.main()

    print("Done. Start the API with: uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
