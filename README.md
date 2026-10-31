# BrightLoop-odoo

A unified software platform that runs the full life of a subscription business—from setting up products and plans to sending invoices, collecting payments, and reporting revenue. Built for the 8-hour Make-a-thon.

## 👥 Team Task Distribution

### Person 1 — Authentication & User Management
- Customer registration and login with secure validation.
- Role-based access control (Admin, Staff, Customer portal).
- Admin-only staff creation and password reset workflows.

### Person 2 — Product, Plans & Pricing
- Product and variant management (e.g., brand-based pricing add-ons).
- Subscription plan creation with daily, weekly, monthly, or yearly frequencies.
- Tax configurations and admin-controlled discount rules.

### Person 3 — Quotations & Subscription Management
- Quotation templates and custom offer lines with validity periods.
- Seamless conversion of confirmed quotations into active subscriptions.
- Unique subscription numbering and lifecycle management (Draft → Quotation → Confirmed → Active → Closed, plus pause/renew controls).

### Person 4 — Billing, Payments & Dashboard
- Automated invoice generation from active subscriptions on billing days.
- Payment recording, outstanding balance tracking, and overdue invoice chasing.
- Comprehensive finance dashboard tracking active subscriptions, revenue, and receivables.

## 🛠️ Tech Stack
- **Frontend**: React + Vite, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Recharts, React Hook Form, Zod
- **Backend**: FastAPI, Python, Pydantic v2, SQLAlchemy 2, Alembic
- **Database**: Supabase PostgreSQL
- **Email**: Resend (for notifications and password resets)
- **Reports**: ReportLab (invoice PDFs)
- **Deployment**: Render Static Site (frontend) & Render Web Service (backend)
- **CI/CD**: GitHub Actions

## 📁 Repository Layout

```
frontend/   React + Vite + TypeScript + Tailwind (P4 finance UI so far)
backend/    FastAPI modular monolith
  app/core/            shared plumbing: config, database (Base), errors, pagination
  app/models/          P2 — catalog tables (products, plans, taxes, discounts)
  app/modules/billing/ P4 — invoices, payments, billing runs, dashboard
  alembic/             single migration tree for the whole monolith
docs/       architecture.md — billing module technical design (P4)
.github/    workflows/billing-cron.yml — scheduled recurring billing (P4)
```

## 🚀 Quickstart

### Backend

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # defaults work out of the box (SQLite + dev auth)
uvicorn app.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- `AUTH_DEV_BYPASS=true` (default) acts as a finance admin — no JWT needed in dev.
- `USE_STUB_PROVIDERS=true` seeds demo customers/subscriptions so the billing
  module runs end-to-end before P1–P3 modules land.
- With Postgres (Supabase), set `DATABASE_URL` and run `alembic upgrade head`.

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api → :8000
```

### Tests

```bash
cd backend && python -m pytest
```

## ⏰ Scheduled billing (GitHub Actions)

`.github/workflows/billing-cron.yml` calls
`POST /api/v1/internal/billing/run` daily at 01:00 UTC with the
`X-Internal-Token` header, looping until `remaining = 0`. Required repo
secrets: `API_BASE_URL`, `INTERNAL_JOB_TOKEN`.
