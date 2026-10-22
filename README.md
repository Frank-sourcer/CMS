# Courier Management System

A full-stack courier API built with FastAPI, PostgreSQL, and vanilla JavaScript. Designed for Kenya, with M-Pesa payments and SMS notifications.

**Live Demo:** https://cms-api-suci.onrender.com/admin-ui
**API Docs:** https://cms-api-suci.onrender.com/docs

> Note: The live demo runs on Render's free tier and may take ~30 seconds to wake up after inactivity.

## Features

- **Auth** — JWT login, role-based access (admin, dispatcher, rider, customer, hub_staff)
- **Customers** — User-linked profiles, individual/business types
- **Riders** — Vehicle info and availability tracking
- **Shipments** — 12-status lifecycle with validated transitions
- **Dispatch** — Rider assignment with multi-leg handoff support
- **Hubs** — Parcel movement between cities
- **Tracking** — Per-shipment event timeline
- **Proof of Delivery** — Signature, OTP, photo, GPS
- **Payments** — Ledger with auto-created pending obligations
- **M-Pesa** — STK Push integration (Lipa na M-Pesa)
- **SMS** — Auto SMS via Africa's Talking on delivery events
- **Admin Dashboard** — Dark-themed web UI
- **REST API** — 60+ endpoints, Swagger docs
- **Tests** — 19 pytest tests covering core flows

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13, FastAPI |
| Database | PostgreSQL (prod), SQLite (dev) |
| ORM | SQLAlchemy 2.x |
| Auth | JWT (python-jose), scrypt hashing |
| Server | Gunicorn + Uvicorn |
| Payments | Safaricom Daraja API |
| SMS | Africa's Talking |
| Frontend | Vanilla HTML/CSS/JS |
| Deployment | Render |
| Testing | pytest, httpx |

---

## Quick Start

### Prerequisites

- Python 3.11+ (3.13 recommended)
- Git

### Clone and Install

    git clone https://github.com/Frank-sourcer/CMS.git
    cd CMS
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

### Environment Variables

Copy the template and fill in values:

    cp .env.example .env

Minimum required:

    SECRET_KEY=your-random-secret-key
    MPESA_CONSUMER_KEY=your-key
    MPESA_CONSUMER_SECRET=your-secret
    MPESA_PASSKEY=your-passkey
    MPESA_CALLBACK_URL=https://your-domain.com/mpesa/callback
    MPESA_SHORTCODE=174379
    MPESA_ENVIRONMENT=sandbox
    AT_USERNAME=sandbox
    AT_API_KEY=your-api-key

Leave `DATABASE_URL` unset for local SQLite.


### Run Locally

    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

- API docs: http://127.0.0.1:8000/docs
- Admin UI: http://127.0.0.1:8000/admin-ui
- Health: http://127.0.0.1:8000/health

### Create First Admin

    python -c "from app.database import SessionLocal; from app.models import User; from app.security import hash_password; db = SessionLocal(); db.add(User(name='Admin', email='admin@cms.local', phone='0700000000', password_hash=hash_password('admin123'), role='admin')); db.commit(); print('Admin created'); db.close()"

Login with `admin@cms.local` / `admin123`.

### Run Tests

    pip install -r requirements-dev.txt
    pytest tests/ -v

---

## Project Structure

    CMS/
    ├── app/
    │   ├── main.py              FastAPI app + router registration
    │   ├── database.py          Engine, session, get_db
    │   ├── models.py            10 SQLAlchemy models
    │   ├── security.py          JWT, hashing, role checks
    │   ├── pagination.py        Generic PaginatedResponse[T]
    │   ├── mpesa.py             Daraja client (lazy init)
    │   ├── sms.py               Africa's Talking wrapper
    │   ├── *_schemas.py         Per-resource Pydantic schemas
    │   └── routers/
    │       ├── auth.py          Login + register
    │       ├── users.py         User CRUD (admin)
    │       ├── customers.py     Customer profiles
    │       ├── riders.py        Rider profiles
    │       ├── shipments.py     Shipments + dispatch + PoD
    │       ├── hubs.py          Hub management
    │       ├── payments.py      Payment ledger
    │       ├── notifications.py Notification log + SMS delivery
    │       ├── mpesa_router.py  STK Push + callback
    │       └── admin.py         Dashboard aggregations
    ├── static/
    │   └── admin.html           Single-file admin dashboard
    ├── tests/
    │   ├── conftest.py          Fixtures (in-memory DB, client)
    │   ├── test_auth.py
    │   ├── test_shipments.py
    │   ├── test_dispatch.py
    │   ├── test_pagination.py
    │   └── test_smoke.py
    ├── requirements.txt
    ├── requirements-dev.txt
    └── .env.example


---

## API Overview

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/auth/login` | POST | Get JWT token |
| `/auth/register` | POST | Public customer signup |
| `/users/` | GET/POST | List/create users (admin) |
| `/customers/` | GET/POST | Customer profiles (paginated) |
| `/riders/` | GET/POST | Rider profiles (paginated) |
| `/shipments/` | GET/POST | Shipments (paginated) |
| `/shipments/{id}/assign` | POST | Assign rider |
| `/shipments/{id}/status` | PATCH | Advance status |
| `/shipments/{id}/arrive/{hub}` | POST | Arrive at hub |
| `/shipments/{id}/depart/{hub}` | POST | Depart from hub |
| `/shipments/{id}/tracking` | GET | Event timeline |
| `/shipments/{id}/pod` | GET/POST | Proof of delivery |
| `/shipments/{id}/pay-mpesa` | POST | Trigger STK Push |
| `/mpesa/callback` | POST | Safaricom webhook |
| `/payments/shipment/{id}` | GET | Payment ledger |
| `/notifications/` | GET | Notification log |
| `/admin/dashboard` | GET | Aggregate stats |
| `/health` | GET | Health check |

Full interactive docs: https://cms-api-suci.onrender.com/docs

---

## Deployment

The app auto-deploys to Render on every push to `main`.

**Environment variables required in production:**

- `SECRET_KEY` — random string
- `DATABASE_URL` — Render Postgres internal URL
- `MPESA_CONSUMER_KEY`, `MPESA_CONSUMER_SECRET`, `MPESA_PASSKEY`
- `MPESA_CALLBACK_URL` — https://your-domain.com/mpesa/callback
- `MPESA_SHORTCODE`, `MPESA_ENVIRONMENT`
- `AT_USERNAME`, `AT_API_KEY`

**Build command:**

    pip install -r requirements.txt

**Start command:**

    gunicorn -w 2 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT

---

## Notes on M-Pesa and SMS

Both integrations currently use **sandbox mode**:

- **M-Pesa**: STK Push works against Safaricom's sandbox shortcode (174379). Callbacks from the sandbox are unreliable by design. Production requires a real Paybill/Till and a Go-Live application.
- **SMS**: Africa's Talking sandbox accepts messages and returns success but only delivers to numbers verified in your sandbox account. Production requires purchasing SMS credits.

## License

MIT
