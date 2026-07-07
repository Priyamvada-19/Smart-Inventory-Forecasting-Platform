# ChainMind — AI Supply Chain Intelligence Platform

An AI-powered supply chain platform: demand forecasting, inventory optimization,
stockout/overstock risk prediction, supplier intelligence, delivery delay
prediction, warehouse optimization, and an AI recommendation engine — with a
React frontend and a FastAPI + MySQL + scikit-learn/XGBoost backend that
actually talk to each other.

## What you have

## ✅ Fully included and working

**All 10 modules, backed by real logic (not just UI mockups):**
Demand Forecast · Inventory · Risk Radar · Suppliers · Delivery Delays ·
Warehouses · Regional & Seasonal · AI Recommendations · Reports · Overview

**Real machine learning on the backend**, trained on synthetically generated
but realistic data (seasonal curves, lead-time math, supplier reliability
patterns):
- XGBoost demand forecasting (global model across products, lag/rolling/seasonal features, recursive multi-step forecast)
- Logistic regression stockout/overstock risk classifiers
- KMeans supplier tier clustering on top of a weighted composite score
- XGBoost delivery delay regression

**Authentication & authorization**
- JWT login/register, real password hashing (bcrypt)
- 4 enforced roles (viewer / analyst / manager / admin) — tested that a viewer is correctly blocked (403) from actions a manager can do
- Real Google ID token verification endpoint on the backend (`POST /auth/google`) — verifies actual token signatures against Google's public certs, not a stub

**Frontend ↔ backend integration is real, not just plausible-looking code**
- Login page tries the real API first; only falls back to in-browser demo data if the backend genuinely isn't reachable
- A visible Live/Demo badge in the header always shows which one you're looking at
- "Add your own product" persists to the real database in live mode and flows through real forecasting/risk logic
- CSV export in the Reports tab downloads a real file from the backend
- Verified with actual HTTP calls (not just in-process testing): booted a real uvicorn server, sent a real CORS preflight, logged in over HTTP, and confirmed every endpoint's JSON shape matches what the frontend expects, field for field

**UI**
- Light/dark theme toggle (mutates a shared token set, no reload needed)
- Deliberately minimal, non-white login screen, no glow/gradient/animated-particle "AI dashboard" clichés
- No watermarks or third-party branding anywhere

**Infrastructure**
- Docker Compose: MySQL 8.0 + API + Adminer, one command to boot
- Auto-seeds synthetic data and auto-trains all models on first run

---

##  Simulated or placeholder (present in the UI, not fully wired)

- **"Continue with Google" button (frontend)** — simulates the flow with a loading state, then logs you in as a demo user. The *backend* verification endpoint is real and working; what's missing is the frontend piece (Google Identity Services script + a registered OAuth Client ID tied to a fixed domain). An artifact preview has no such fixed origin, which is why this wasn't completed end-to-end.
- **"Executive Summary" and "Supplier Scorecard" report buttons** — visible in the Reports tab, not wired to generate anything yet. Only "Inventory Detail" (CSV) actually works.
- **Search bar and notification bell (top bar)** — visual only, not wired to real search or a notification panel.

## ❌ Not included (out of scope by design)

Left out to keep the backend reviewable in one sitting rather than sprawling:

- Automated tests (no pytest suite or CI pipeline) — everything was verified manually and thoroughly during development, but there's no test suite living in the repo
- Alembic database migrations (schema changes currently require recreating tables)
- Redis caching / API rate limiting
- Background job scheduling for periodic retraining (models are retrained manually via `python -m app.ml.train_all`)
- Kubernetes manifests (Docker Compose only)
- WebSocket/SSE live updates (dashboard refreshes on demand, not push-based)
- Multi-tenancy (single organization per deployment)
- Audit logging (who-changed-what-when)
- Admin UI for user management (use `/docs` or direct API calls)

## Known issue

The synthetic data generator currently flags most sample SKUs as
stockout-risk. This is a data-tuning imbalance, not a functional bug — the
pipeline runs correctly end-to-end — but it can look visually unbalanced to
a reviewer. Adjustable in `app/data_gen.py` (the current-stock multiplier
range) if you want a healthier-looking mix before presenting this.

---

## Quickstart

**Backend:**
```bash
cd chainmind-backend
cp .env.example .env
docker compose up --build
```
Visit `http://localhost:8000/docs` (API) or `http://localhost:8080` (Adminer, DB browser).

Default login: `admin@chainmind.local` / `ChangeMe123!` — **change this before any real deployment.**

---

## Tech stack

**Frontend:** React, Recharts, Tailwind, lucide-react
**Backend:** FastAPI, SQLAlchemy 2.0, MySQL 8.0, scikit-learn, XGBoost, JWT (python-jose + passlib), Docker Compose

## Architecture

```
app/
├── main.py                FastAPI app + router registration + CORS
├── config.py               Settings (env vars via pydantic-settings)
├── database.py              SQLAlchemy engine/session
├── models.py                 ORM models: User, Product, Supplier, Warehouse,
│                              Inventory, SalesRecord, Region, Shipment, Alert
├── schemas.py                 Pydantic request/response models
├── security.py                 Password hashing, JWT issuance, RBAC dependency
├── data_gen.py                  Synthetic data generator + DB seeding
├── ml/
│   ├── forecasting.py            XGBoost demand forecasting
│   ├── risk.py                     Logistic regression risk classifiers
│   ├── supplier_scoring.py           Weighted score + KMeans tiering
│   ├── delay_prediction.py             XGBoost delivery delay regressor
│   └── train_all.py                     Orchestrates training of everything
└── routers/                    auth, products, suppliers, warehouses,
                                 inventory, forecast, risk, delivery,
                                 recommendations, reports, regions
```

## Auth & roles

| Role      | Can do |
|-----------|--------|
| `viewer`  | Read-only: dashboards, forecasts, reports |
| `analyst` | + refresh delivery delay predictions |
| `manager` | + create/update products, suppliers, inventory; recompute supplier tiers |
| `admin`   | + delete products, full access |

## Google sign-in setup (to make it fully real, it is yet to be implemented)

1. Create an OAuth 2.0 Client ID (Web application) in Google Cloud Console, with your frontend's exact URL under "Authorized JavaScript origins".
2. Set `GOOGLE_CLIENT_ID` in the backend's `.env`.
3. On the frontend, load `https://accounts.google.com/gsi/client`, call `google.accounts.id.initialize({ client_id, callback })`, and in the callback POST `{ id_token: response.credential }` to `POST /auth/google`.
4. Swap out `handleGoogle` in `chainmind-control.jsx` for this real flow.

## Why the ML is structured this way

- **Demand forecasting** is one global XGBoost model across all products (not one per SKU) so it can borrow seasonal/category patterns even where a single SKU's own history is short.
- **Risk classifiers** are logistic regression models *bootstrapped* from business rules rather than hardcoded thresholds — smoother probabilities, and a natural place to plug in real historical outcomes later.
- **Supplier tiers** combine a transparent weighted score with KMeans clustering, so tier boundaries adapt to the whole supplier base rather than a fixed cutoff.
- **Delivery delay** is a straightforward XGBoost regression on supplier reliability + shipment features.

Retrain everything anytime:
```bash
docker compose exec api python -m app.ml.train_all
```
# Smart-Inventory-Forecasting-Platform

(This a working website with few features that will be added later)
