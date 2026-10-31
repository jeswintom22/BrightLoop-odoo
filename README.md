# BrightLoop Odoo

**BrightLoop Odoo** is an enterprise-grade Billing, Subscription Management, and Financial Intelligence platform built with a modern decoupled architecture. It combines a robust **FastAPI** backend with a high-performance **React / Next.js** frontend, offering real-time financial analytics, automated billing runs, multi-channel notification engine, and an integrated AI-driven finance copilot.

---

## 🏗️ Architecture Overview

The application follows a modular, domain-driven monorepo architecture:

```
BrightLoop-odoo/
├── backend/                  # FastAPI Application Core
│   ├── alembic/              # Database schema migrations
│   ├── app/
│   │   ├── api/              # Core API endpoints & health checks
│   │   ├── core/             # Configuration, database session, errors, time & pagination
│   │   ├── models/           # Declarative database models (Products, Plans, Taxes, Notifications)
│   │   ├── modules/          # Domain-driven feature modules
│   │   │   ├── analytics/    # Product & subscription metrics
│   │   │   ├── auth/         # Authentication, user management, and portal access
│   │   │   ├── billing/      # Invoices, payments, PDF generation, and accounting integrations
│   │   │   ├── finance_intelligence/ # MRR/ARR, forecasting, risk detection & AI Copilot
│   │   │   └── subscriptions/# Subscription lifecycle & automated workflows
│   │   ├── routers/          # Framework route handlers
│   │   └── services/         # Business logic layer
│   └── tests/                # Automated unit & integration test suites
├── frontend/                 # React (Vite + Tailwind CSS + Shadcn UI) dashboard
├── frontend-next/            # Next.js App Router application (Portal & Web views)
├── docs/                     # Architecture & audit documentation
└── render.yaml               # Cloud deployment configuration
```

---

## ✨ Key Features

### 1. Subscription & Billing Lifecycle
* **Subscription Management:** Automated recurring billing cycles, plan upgrades/downgrades, and status tracking.
* **Invoicing & Payments:** Flexible invoicing engine with automatic PDF generation, tax calculations, dynamic discounting, and payment processing hooks.
* **Automated Cron Workflows:** GitHub Actions / Background tasks for scheduled billing runs and notification retries.

### 2. Financial Intelligence & AI Copilot
* **MRR & ARR Analytics:** Real-time metrics for Monthly Recurring Revenue (MRR), Annual Recurring Revenue (ARR), and churn rates.
* **Financial Forecasting:** Deterministic analytics and forecasting models computed in Python/SQL.
* **AI Copilot & Risk Detection:** OpenAI-powered financial insights, revenue leak detection, and automated risk summaries for active subscriptions.

### 3. Multi-Channel Notifications
* Granular notification delivery pipeline supporting administrative webhooks, customer emails, and user notification preference management.

---

## 🚀 Tech Stack

* **Backend:** Python 3.10+, FastAPI, SQLAlchemy, Alembic, Pydantic, PostgreSQL (`postgres_fdw`, `jsonb`), Pytest.
* **Frontend:** React, Next.js (App Router), TypeScript, Tailwind CSS, Vite.
* **DevOps & Infrastructure:** GitHub Actions (CI/CD), Docker / Render (`render.yaml`).

---

## 🛠️ Getting Started

### Prerequisites

* **Python:** `3.10` or higher
* **Node.js:** `18.x` or higher
* **PostgreSQL:** `14+` with native `jsonb` support

---

### Backend Setup

1. **Navigate to the backend folder:**
   ```bash
   cd backend
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

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

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   *Update `.env` with your PostgreSQL connection strings, OpenAI API key, and JWT secret key.*

5. **Run database migrations:**
   ```bash
   alembic upgrade head
   ```

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

---

### Frontend Setup (Vite / React Dashboard)

1. **Navigate to the frontend folder:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```

---

### Frontend-Next Setup (Next.js Application)

1. **Navigate to the Next.js directory:**
   ```bash
   cd frontend-next
   ```

2. **Install dependencies and start server:**
   ```bash
   npm install
   npm run dev
   ```

---

## 🧪 Running Tests

Execute the full backend unit and integration test suite via `pytest`:

```bash
cd backend
pytest
```

- `true` (default): in-memory demo data — full E2E without P1–P3 tables.
- `false`: real providers — `DbPricingProvider` reads P2's catalog now
  (products → `sales_price`, `tax_id` → `tax_configurations`, `discounts` via
  `discount_products`); `DbSubscriptionProvider`/`DbCustomerProvider` query
  the contract tables (`subscriptions`, `subscription_items`, `customers`)
  described in `docs/architecture.md` §7.
