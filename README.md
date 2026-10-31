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
frontend/       React + Vite + TypeScript + Tailwind — canonical UI (P4 finance so far)
frontend-next/  Next.js + Supabase-JS auth UI (P1) — parked until the team
                picks one frontend stack; not part of the build/deploy
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
secrets: `API_BASE_URL`, `INTERNAL_JOB_TOKEN`. The same workflow then runs
`POST /api/v1/internal/notifications/run` to send due reminders.
`.github/workflows/notification-retries.yml` checks for due email retries
every 15 minutes.

## Email notifications

Apply migrations with `alembic upgrade head`. Configure `RESEND_API_KEY` and
`RESEND_WEBHOOK_SECRET` in the backend environment, and configure the Resend
webhook to call `/api/v1/webhooks/resend` for delivery events. `RESEND_FROM`
is the fallback sender; an administrator can save sender details in
Notification admin. Retry limits and delay are controlled by
`NOTIFICATION_MAX_ATTEMPTS` and `NOTIFICATION_RETRY_DELAY_MINUTES`.

The admin notification API is role-restricted to `admin`; customer email
addresses and delivery history are available only through those authorized
endpoints. Production scheduled notifications require the real customer,
subscription, and pricing providers; email sending is blocked in production
while stub providers are configured.

## 🚢 Deployment (Render + Supabase)

`render.yaml` is a Render **Blueprint**: one web service (`brightloop-api`,
uvicorn) + one static site (`brightloop-frontend`, Vite build) wired with a
`/api/*` rewrite to the API.

1. **Supabase**: create a project → Settings → Database → copy the
   *transaction pooler* URI (port 6543) for the web service `DATABASE_URL`;
   use the *direct* URI (port 5432) when running migrations manually.
2. **Render**: New → Blueprint → select this repo. Set the `sync: false`
   secrets in the dashboard: `DATABASE_URL`, `RESEND_API_KEY`,
   `RESEND_WEBHOOK_SECRET`, `FRONTEND_URL`, `CORS_ORIGINS`,
   `INTERNAL_JOB_TOKEN`, and `VITE_API_BASE_URL` if the API is hosted
   separately.
3. **Migrate**: run `alembic upgrade head` once against the direct URI
   (Render Shell, CI, or locally with `DATABASE_URL` set).
4. **Cron**: set GitHub secrets `API_BASE_URL` (e.g.
   `https://brightloop-api.onrender.com`) and `INTERNAL_JOB_TOKEN` (same value
   as the Render env var) for the billing and notification workflows.

### Cross-module providers

`backend/app/deps.py` switches providers via `USE_STUB_PROVIDERS`:

- `true` (default): in-memory demo data — full E2E without P1–P3 tables.
- `false`: real providers — `DbPricingProvider` reads P2's catalog now
  (products → `sales_price`, `tax_id` → `tax_configurations`, `discounts` via
  `discount_products`); `DbSubscriptionProvider`/`DbCustomerProvider` query
  the contract tables (`subscriptions`, `subscription_items`, `customers`)
  described in `docs/architecture.md` §7.
