from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict

from app.models import UserRole


# ---------- Auth ----------
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.viewer


class GoogleLoginRequest(BaseModel):
    id_token: str  # the credential returned by Google Identity Services on the frontend


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: EmailStr
    role: UserRole
    is_active: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole


# ---------- Suppliers ----------
class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    region: Optional[str]
    category: Optional[str]
    on_time_rate: float
    defect_rate: float
    avg_lead_time_days: int
    cost_index: float
    responsiveness: float
    fill_rate: float
    score: float
    tier: str


class SupplierCreate(BaseModel):
    name: str
    region: str
    category: str
    on_time_rate: float = 90.0
    defect_rate: float = 1.0
    avg_lead_time_days: int = 14
    cost_index: float = 1.0
    responsiveness: float = 80.0
    fill_rate: float = 95.0


# ---------- Warehouses ----------
class WarehouseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    region: Optional[str]
    capacity_units: int
    current_utilization_pct: float
    throughput_per_day: int
    pick_accuracy_pct: float
    labor_efficiency_pct: float
    status: str


# ---------- Products ----------
class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sku: str
    name: str
    category: str
    unit_cost: float
    unit_price: float
    lead_time_days: int
    safety_stock: int
    reorder_point: int
    supplier_id: Optional[int]


class ProductCreate(BaseModel):
    sku: str
    name: str
    category: str
    unit_cost: float
    unit_price: float
    lead_time_days: int = 14
    supplier_id: Optional[int] = None


# ---------- Inventory ----------
class InventoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    warehouse_id: int
    current_stock: int


class InventoryCreate(BaseModel):
    product_id: int
    warehouse_id: int
    current_stock: int = 0


class InventoryUpdate(BaseModel):
    current_stock: int


class ReorderRecommendation(BaseModel):
    product_id: int
    sku: str
    name: str
    current_stock: int
    avg_daily_demand: float
    days_of_supply: float
    lead_time_days: int
    reorder_point: int
    suggested_reorder_qty: int
    status: str  # stockout-risk / dead-stock / overstock / healthy


# ---------- Forecasting ----------
class ForecastPoint(BaseModel):
    period: str
    predicted_units: float
    lower_bound: float
    upper_bound: float


class HistoryPoint(BaseModel):
    period: str
    actual_units: float


class ForecastResponse(BaseModel):
    product_id: int
    sku: str
    name: str
    history_avg_monthly: float
    history: List[HistoryPoint]
    forecast: List[ForecastPoint]


# ---------- Regions ----------
class RegionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    weather_pattern: Optional[str]
    demand_index: float
    growth_rate_pct: float


class RegionMonthlyPoint(BaseModel):
    period: str
    quantity: float


# ---------- Risk ----------
class RiskSummary(BaseModel):
    product_id: int
    sku: str
    name: str
    days_of_supply: float
    stockout_probability: float
    overstock_probability: float
    status: str


# ---------- Delivery ----------
class ShipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reference: str
    supplier_id: int
    warehouse_id: int
    eta_days: int
    predicted_delay_days: float
    risk_level: str
    status: str


# ---------- Recommendations ----------
class Recommendation(BaseModel):
    category: str
    title: str
    detail: str
    impact: str
    severity: str


# ---------- Reports ----------
class DashboardSummary(BaseModel):
    forecast_accuracy_pct: float
    stockout_risk_skus: int
    dead_or_overstock_skus: int
    avg_supplier_score: float
    avg_warehouse_utilization: float
    active_alerts: int
