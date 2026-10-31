# BrightLoop-odoo

A unified software platform that runs the full life of a subscription business—from setting up products and plans to sending invoices, collecting payments, and reporting revenue[cite: 1]. Built for the 8-hour Make-a-thon[cite: 1].

## 👥 Team Task Distribution

### Person 1 — Authentication & User Management
- Customer registration and login with secure validation[cite: 2].
- Role-based access control (Admin, Staff, Customer portal)[cite: 2].
- Admin-only staff creation and password reset workflows[cite: 2].

### Person 2 — Product, Plans & Pricing
- Product and variant management (e.g., brand-based pricing add-ons)[cite: 3].
- Subscription plan creation with daily, weekly, monthly, or yearly frequencies[cite: 3].
- Tax configurations and admin-controlled discount rules[cite: 3, 4].

### Person 3 — Quotations & Subscription Management
- Quotation templates and custom offer lines with validity periods[cite: 3].
- Seamless conversion of confirmed quotations into active subscriptions[cite: 3].
- Unique subscription numbering and lifecycle management (Draft $\rightarrow$ Quotation $\rightarrow$ Confirmed $\rightarrow$ Active $\rightarrow$ Closed, plus pause/renew controls)[cite: 3].

### Person 4 — Billing, Payments & Dashboard
- Automated invoice generation from active subscriptions on billing days[cite: 3, 4].
- Payment recording, outstanding balance tracking, and overdue invoice chasing[cite: 4].
- Comprehensive finance dashboard tracking active subscriptions, revenue, and receivables[cite: 4].

## 🛠️ Tech Stack
- **Frontend**: Next.js, TypeScript, Tailwind CSS, shadcn/ui, Recharts
- **Backend**: FastAPI, Python, Pydantic v2, SQLAlchemy 2, Alembic
- **Database**: Supabase PostgreSQL
- **Email**: Resend (for notifications and password resets)
- **Deployment**: Vercel (Frontend) & Render (Backend)
- **CI/CD**: GitHub Actions