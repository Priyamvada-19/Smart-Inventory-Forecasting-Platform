"""
Generates realistic synthetic supply-chain data and seeds the database with it.
The seasonal/trend logic mirrors the frontend demo so numbers tell a consistent story
end-to-end, but every value here is generated independently in Python.
"""
import random
import math
from datetime import datetime
from dateutil.relativedelta import relativedelta

from sqlalchemy.orm import Session

from app import models

random.seed(42)

SEASONAL_CURVES = {
    "holiday": [0.7, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.1, 1.3, 1.7, 2.1],
    "winter":  [1.6, 1.4, 1.1, 0.8, 0.6, 0.5, 0.5, 0.55, 0.7, 1.0, 1.4, 1.7],
    "summer":  [0.6, 0.65, 0.8, 1.1, 1.5, 1.8, 1.9, 1.7, 1.2, 0.8, 0.6, 0.55],
    "monsoon": [0.5, 0.5, 0.6, 0.7, 1.3, 1.9, 2.0, 1.6, 1.0, 0.6, 0.5, 0.5],
    "flat":    [0.95, 0.9, 1.0, 1.0, 1.05, 1.0, 0.95, 1.0, 1.05, 1.05, 1.0, 1.1],
}

PRODUCT_DEFS = [
    ("P-1042", "Aria Wireless Earbuds", "Electronics", 22, 59, 12, "holiday"),
    ("P-2081", "Kelvin Smart Thermostat", "Electronics", 34, 89, 18, "winter"),
    ("P-3117", "Everline Cotton Tee", "Apparel", 4.2, 14, 25, "summer"),
    ("P-3355", "Basecamp Rain Shell", "Apparel", 18, 64, 30, "monsoon"),
    ("P-4210", "Harvest Organic Oats 1kg", "Grocery", 1.8, 4.5, 7, "flat"),
    ("P-4488", "Solstice Cold Brew Pack", "Grocery", 2.4, 6.2, 6, "summer"),
    ("P-5501", "Nimbus Air Purifier", "Home", 46, 129, 21, "winter"),
    ("P-5622", "Ledger Desk Lamp", "Home", 9, 28, 15, "flat"),
]

SUPPLIER_DEFS = [
    ("Vertex Components Ltd", "East Asia", "Electronics"),
    ("Northgate Textiles", "South Asia", "Apparel"),
    ("Pacific Harvest Co-op", "Southeast Asia", "Grocery"),
    ("Ironclad Home Goods", "Eastern Europe", "Home"),
    ("BrightPath Electronics", "North America", "Electronics"),
    ("Solara Apparel Group", "South Asia", "Apparel"),
]

WAREHOUSE_DEFS = [
    ("ChainMind North DC", "North"),
    ("ChainMind West Hub", "West"),
    ("ChainMind South DC", "South"),
    ("ChainMind East Hub", "East"),
    ("ChainMind Central Fulfillment", "Central"),
]

REGION_DEFS = [
    ("North", "Cold winters"),
    ("West", "Dry heat"),
    ("South", "Monsoon"),
    ("East", "Humid"),
    ("Central", "Temperate"),
]


def _score_and_tier(on_time, defect, responsiveness, fill_rate):
    score = round(on_time * 0.35 + (100 - defect * 8) * 0.25 + responsiveness * 0.2 + fill_rate * 0.2, 1)
    tier = "Preferred" if score >= 80 else "Standard" if score >= 65 else "At Risk"
    return score, tier


def seed_database(db: Session, months_of_history: int = 24) -> None:
    if db.query(models.Product).count() > 0:
        return  # already seeded

    # Regions
    regions = []
    for name, weather in REGION_DEFS:
        r = models.Region(
            name=name, weather_pattern=weather,
            demand_index=round(70 + random.random() * 55, 1),
            growth_rate_pct=round(random.uniform(-6, 18), 1),
        )
        db.add(r)
        regions.append(r)
    db.flush()

    # Suppliers
    suppliers = []
    for name, region, category in SUPPLIER_DEFS:
        on_time = round(72 + random.random() * 26, 1)
        defect = round(0.5 + random.random() * 4.5, 2)
        responsiveness = round(60 + random.random() * 38, 1)
        fill_rate = round(85 + random.random() * 14, 1)
        score, tier = _score_and_tier(on_time, defect, responsiveness, fill_rate)
        s = models.Supplier(
            name=name, region=region, category=category,
            on_time_rate=on_time, defect_rate=defect,
            avg_lead_time_days=random.randint(6, 30),
            cost_index=round(0.8 + random.random() * 0.5, 2),
            responsiveness=responsiveness, fill_rate=fill_rate,
            score=score, tier=tier,
        )
        db.add(s)
        suppliers.append(s)
    db.flush()

    # Warehouses
    warehouses = []
    for name, region in WAREHOUSE_DEFS:
        utilization = round(38 + random.random() * 60, 1)
        status = "over-capacity" if utilization > 90 else "under-utilized" if utilization < 45 else "optimal"
        w = models.Warehouse(
            name=name, region=region,
            capacity_units=random.randint(40000, 70000),
            current_utilization_pct=utilization,
            throughput_per_day=random.randint(1200, 3400),
            pick_accuracy_pct=round(94 + random.random() * 5.5, 1),
            labor_efficiency_pct=round(70 + random.random() * 26, 1),
            status=status,
        )
        db.add(w)
        warehouses.append(w)
    db.flush()

    # Products (supplier assigned by matching category where possible)
    products = []
    for sku, name, category, cost, price, lead_time, seasonal in PRODUCT_DEFS:
        matching = [s for s in suppliers if s.category == category]
        supplier = random.choice(matching) if matching else random.choice(suppliers)
        p = models.Product(
            sku=sku, name=name, category=category, unit_cost=cost, unit_price=price,
            lead_time_days=lead_time, supplier_id=supplier.id,
        )
        db.add(p)
        products.append((p, seasonal))
    db.flush()

    # Sales history -- this is the ML training data
    start = datetime.utcnow().replace(day=1) - relativedelta(months=months_of_history)
    for p, seasonal in products:
        curve = SEASONAL_CURVES[seasonal]
        base = 120 + random.random() * 260
        trend = 1 + (random.random() - 0.35) * 0.35
        for region in regions:
            region_weight = 0.5 + random.random()  # some regions sell more of this product than others
            for m in range(months_of_history):
                period = start + relativedelta(months=m)
                month_idx = period.month - 1
                trend_factor = 1 + ((trend - 1) * (m / max(months_of_history - 1, 1)))
                noise = 0.9 + random.random() * 0.2
                promo = random.random() < 0.12
                promo_lift = 1.25 if promo else 1.0
                competitor_ratio = round(0.85 + random.random() * 0.3, 2)
                weather_index = round(curve[month_idx] * (0.9 + random.random() * 0.2), 2)
                qty = max(0, round(base * curve[month_idx] * trend_factor * noise * region_weight * promo_lift))
                db.add(models.SalesRecord(
                    product_id=p.id, region_id=region.id, period=period,
                    quantity_sold=qty, promotion_active=promo,
                    competitor_price_ratio=competitor_ratio, weather_index=weather_index,
                ))

        # Current inventory position across a couple of warehouses
        recent_avg = base * curve[start.month - 1] * (1 + (trend - 1) * 0.8)
        daily_demand = recent_avg / 30
        safety_stock = round(daily_demand * p.lead_time_days * 0.5)
        reorder_point = round(daily_demand * p.lead_time_days + safety_stock)
        p.safety_stock = safety_stock
        p.reorder_point = reorder_point
        for w in random.sample(warehouses, k=2):
            stock = round(reorder_point * (0.3 + random.random() * 1.5))
            db.add(models.Inventory(product_id=p.id, warehouse_id=w.id, current_stock=stock))

    # Shipments
    n = 0
    for i, s in enumerate(suppliers):
        for j, w in enumerate(warehouses):
            if (i + j) % 2 == 0:
                base_risk = (100 - s.on_time_rate) / 100
                predicted_delay = round(base_risk * 6 + random.random() * 3, 1)
                risk = "high" if predicted_delay >= 5 else "medium" if predicted_delay >= 2 else "low"
                db.add(models.Shipment(
                    reference=f"SH-{1000+n}", supplier_id=s.id, warehouse_id=w.id,
                    eta_days=random.randint(3, 13), predicted_delay_days=predicted_delay,
                    risk_level=risk, status="in_transit",
                ))
                n += 1

    db.commit()
