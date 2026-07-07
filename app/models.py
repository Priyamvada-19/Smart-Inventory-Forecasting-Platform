import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, Text
)
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"          # full access, user management
    manager = "manager"      # create/edit products, suppliers, warehouses, approve reorders
    analyst = "analyst"      # read + reports + forecasting tools
    viewer = "viewer"        # read-only dashboards


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(128), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    auth_provider = Column(String(16), default="local")  # local / google
    role = Column(Enum(UserRole), default=UserRole.viewer, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Region(Base):
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), unique=True, nullable=False)
    weather_pattern = Column(String(64))
    demand_index = Column(Float, default=100.0)
    growth_rate_pct = Column(Float, default=0.0)

    sales = relationship("SalesRecord", back_populates="region")


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    region = Column(String(64))
    category = Column(String(64))
    on_time_rate = Column(Float, default=90.0)          # % of shipments on time
    defect_rate = Column(Float, default=1.0)            # % defective units
    avg_lead_time_days = Column(Integer, default=14)
    cost_index = Column(Float, default=1.0)              # relative to category average
    responsiveness = Column(Float, default=80.0)          # 0-100
    fill_rate = Column(Float, default=95.0)               # % of orders fully filled
    score = Column(Float, default=0.0)                    # computed composite score
    tier = Column(String(32), default="Standard")          # Preferred / Standard / At Risk
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    products = relationship("Product", back_populates="supplier")
    shipments = relationship("Shipment", back_populates="supplier")


class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    region = Column(String(64))
    capacity_units = Column(Integer, default=50000)
    current_utilization_pct = Column(Float, default=60.0)
    throughput_per_day = Column(Integer, default=1500)
    pick_accuracy_pct = Column(Float, default=97.0)
    labor_efficiency_pct = Column(Float, default=80.0)
    status = Column(String(32), default="optimal")  # optimal / over-capacity / under-utilized

    inventory_items = relationship("Inventory", back_populates="warehouse")
    shipments = relationship("Shipment", back_populates="warehouse")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(32), unique=True, index=True, nullable=False)
    name = Column(String(128), nullable=False)
    category = Column(String(64), nullable=False)
    unit_cost = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    lead_time_days = Column(Integer, default=14)
    safety_stock = Column(Integer, default=0)
    reorder_point = Column(Integer, default=0)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))

    supplier = relationship("Supplier", back_populates="products")
    inventory_items = relationship("Inventory", back_populates="product")
    sales = relationship("SalesRecord", back_populates="product")


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    current_stock = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("Product", back_populates="inventory_items")
    warehouse = relationship("Warehouse", back_populates="inventory_items")


class SalesRecord(Base):
    """One row per product per month per region -- the training data for demand forecasting."""
    __tablename__ = "sales_records"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    period = Column(DateTime, nullable=False)  # first day of the month
    quantity_sold = Column(Integer, nullable=False)
    promotion_active = Column(Boolean, default=False)
    competitor_price_ratio = Column(Float, default=1.0)  # our price / competitor price
    weather_index = Column(Float, default=1.0)

    product = relationship("Product", back_populates="sales")
    region = relationship("Region", back_populates="sales")


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    reference = Column(String(32), unique=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"))
    eta_days = Column(Integer, default=7)
    predicted_delay_days = Column(Float, default=0.0)
    risk_level = Column(String(16), default="low")  # low / medium / high
    status = Column(String(24), default="in_transit")

    supplier = relationship("Supplier", back_populates="shipments")
    warehouse = relationship("Warehouse", back_populates="shipments")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String(32))   # stockout / dead_stock / supplier / warehouse / delivery
    severity = Column(String(16))     # critical / warning / info
    message = Column(Text)
    entity_ref = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)
