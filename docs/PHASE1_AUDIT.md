# Phase 1 Audit — BrightLoop Subscription Management System

Audit of the repository **before** this implementation pass.
**Post-implementation statuses and evidence: see .** Statuses:
COMPLETE / PARTIAL / MISSING / BROKEN / BLOCKED.

## Module inventory (verified by inspection, not just file presence)

| Module | Code present | Verdict |
|---|---|---|
| P1 — Auth & Users | `app/modules/auth/` is an **empty package**; `frontend-next/` holds a parked Next.js scaffold (no backend); no users/customers tables, no JWT issuance, no RBAC enforcement | **MISSING** |
| P2 — Products/Plans/Pricing | `app/models/` (product, variant, plan, tax, discount, discount_products) + `app/routers/products.py`, `product_variants.py` + `ProductService` | **PARTIAL** — no plan/tax/discount APIs; routers have **no auth** |
| P3 — Quotations & Subscriptions | `app/modules/subscriptions/` **empty**; no models/services/routers | **MISSING** |
| P4 — Billing & Dashboard | `app/modules/billing/` complete; 43 tests green | **COMPLETE** (contract-level), pending real-module integration |
| Integration | `integrations_db.py` adapters exist for P2 (live) and P1/P3 contracts (unexercised); `USE_STUB_PROVIDERS=true` default | **PARTIAL** — real paths unproven |

## P1 — Authentication & User Management

| Requirement | Status | Notes |
|---|---|---|
| Customer registration/login | MISSING | no endpoint, no users table |
| Unique email | MISSING | — |
| Password policy (>8 chars, upper, lower, special) | MISSING | **discrepancy**: task allocation says "minimum 8"; original spec says "more than 8" → implement ≥9 and document |
| Forgot/reset password (secure, time-limited, single-use, non-revealing) | MISSING | — |
| RBAC admin/staff/customer | MISSING | `deps.get_current_user` decodes JWT + `require_roles` exist but billing roles were `admin/finance/viewer`; no user source |
| Admin-only staff creation | MISSING | — |
| Customer/staff management | MISSING | — |
| Customer portal (own subscriptions/invoices/payments) | MISSING | — |
| Data isolation (customers can't reach others' records) | MISSING | — |

## P2 — Product, Plans & Pricing

| Requirement | Status | Notes |
|---|---|---|
| Product CRUD (+variants, deactivate) | COMPLETE | `ProductService` + routers verified by tests |
| Variant pricing | PARTIAL | variant has `sales_price`; no "adds ₹X to base" delta pricing — interpret: variant `sales_price` is the final price (documented) |
| Subscription plan CRUD (daily/weekly/monthly/yearly, min qty, availability dates, lifecycle flags) | MISSING | model exists, **no API** |
| Tax config (admin rules, product link) | MISSING | model exists, **no API** |
| Discounts (fixed/%/min purchase/min qty/dates/usage limits/product-scoped) | MISSING | model exists (no min-quantity field — **gap**), **no API** |
| Historical invoice prices immutable | COMPLETE | invoice lines snapshot unit_price/tax/discount at generation |

## P3 — Quotations & Subscriptions

**MISSING entirely** — no models, services, routers. `subscription_items`/`subscriptions` contract tables only exist as an adapter expectation in `integrations_db.py`.

## P4 — Billing, Payments & Dashboard

| Requirement | Status | Notes |
|---|---|---|
| Invoice generation + lifecycle (draft→confirmed→paid, cancel) | COMPLETE | unique (subscription, period) idempotency verified |
| Recurring billing (4 frequencies, due scan, date advance, idempotent, manual+GHA) | COMPLETE | verified live + tests |
| Payments (methods, partial, outstanding, void, idempotency) | COMPLETE | hardened last pass (409 conflicts, race-safe) |
| Dashboard (subs/revenue/outstanding/overdue/recent/trend/filters) | COMPLETE | trend baseline fixed |
| PDF + email | COMPLETE | ReportLab + Resend (no-op without key) |

## Cross-module integration

| Check | Status |
|---|---|
| Same DB / one Alembic chain | COMPLETE (11 tables, 1 head) |
| P2→P4 real pricing | COMPLETE (DbPricingProvider) |
| P1→all (authz) | MISSING — no users source; billing roles misaligned (finance/viewer vs admin/staff/customer) |
| P3→P4 real subscriptions | MISSING — contract adapter ready, tables absent |
| P4→P1 portal | MISSING |
| ID type agreement | PARTIAL — P2 uses int PKs; billing FKs are UUID; `invoice_lines.product_id` needs int alignment |

## Technical quality

| Area | Status |
|---|---|
| Error envelope / validation | COMPLETE |
| Money = NUMERIC/Decimal | COMPLETE |
| Transactions (invoice gen, payments, date advance) | COMPLETE |
| No destructive init | COMPLETE (Alembic only) |
| CORS / internal-token security | COMPLETE |
| Secrets | COMPLETE (env-only, `.env` gitignored) |
| Pagination / indexes | COMPLETE |

## Completion (pre-implementation)

Verified-complete requirements ≈ **38%** (P4 ~100%, P2 ~35%, P1/P3 ~0%).
