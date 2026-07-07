from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import (
    auth, products, suppliers, warehouses, inventory,
    forecast, risk, delivery, recommendations, reports, regions,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ChainMind Supply Chain Intelligence API",
    description="AI-powered demand forecasting, inventory optimization, supplier "
                "intelligence, and delivery risk prediction for end-to-end supply "
                "chain operations.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your frontend origin(s) in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(suppliers.router)
app.include_router(warehouses.router)
app.include_router(inventory.router)
app.include_router(forecast.router)
app.include_router(risk.router)
app.include_router(delivery.router)
app.include_router(recommendations.router)
app.include_router(reports.router)
app.include_router(regions.router)


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok"}
