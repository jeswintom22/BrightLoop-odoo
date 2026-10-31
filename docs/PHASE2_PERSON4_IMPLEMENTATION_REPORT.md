# Phase 2 — Person 4 Implementation Report

Revenue Intelligence & AI Finance Copilot for the BrightLoop Subscription
Management System. Extends Phase 1 (`docs/PHASE1_AUDIT.md`) — no billing,
invoice, payment or dashboard functionality was rebuilt or replaced.

**Result: all backend endpoints and the frontend UI are functional and
covered by automated tests (164 passed).** Items below distinguish shipped
functionality from interim integrations and known limitations.

---

## 1. Completed

### Revenue intelligence (deterministic, real DB records)

- **MRR/ARR** — `analytics/mrr_arr.py`. Active-status subscriptions only;
  per-cycle `Σ qty × unit_price` pre-tax; normalization
  `daily ×365/12 · weekly ×52/12 · monthly ×1 · yearly ÷12`;
  `ARR = MRR ×12`. Snapshot + month-end trend + by-plan/by-frequency
  breakdowns. Never derived from invoice totals.
- **Revenue trends** — `analytics/revenue.py`. `invoiced`
  (confirmed+paid, by `issue_date`) and `collected` (posted payments, by
  `paid_at`) always separate; day/week/month/year buckets
  (SQLite `strftime` / Postgres `date_trunc`); same-length previous-period
  comparison; growth % = `null` when previous = 0.
- **Breakdowns** — plan, product (line-level), customer, billing period,
  payment method (cash). Real joins across `invoices`, `invoice_lines`,
  `subscriptions`, `subscription_plans`, `products`, `customers`.
- **Forecast** — `analytics/forecasting.py`. Expected billings from active
  subscriptions' `next_billing_date` inside horizon; expected collections =
  outstanding due × realized 90-day collection rate (clamped [0,1]).
  Explicitly labelled heuristic — no ML claims.
- **Risk detection** — `analytics/risk_detection.py`. Five deterministic
  rules (high-value overdue ≥₹10k, multiple overdue, repeated late
  payments, renewal-with-unpaid, large exposure vs capacity) with
  documented severity scoring. Cancelled/settled rows never risk.
- **Performance report** — `analytics/reports.py` /
  `GET /reports/performance`: period totals, previous-period comparison,
  collection rate, MRR/ARR, plan revenue.

### AI layer

- **Provider abstraction** — `ai/provider.py`: `openai`/`gemini` HTTP
  providers + `TemplateProvider` fallback; explicit `AI_TIMEOUT_S`;
  `LLMError` degradation; per-user `RateLimiter` (429 on abuse).
- **Copilot** — `ai/copilot.py`: keyword intent → verified metrics →
  grounded prose. No DB access, no SQL generation, prompt-injection
  containment (`<user_question>` data block + system rules), missing-data
  declared not invented, `provider`/`model`/`sources`/`range` returned with
  every answer.
- **Risk explanations** — `ai/risk_explainer.py`: explains deterministic
  records; grounded template fallback always works.
- **Financial summaries** — `service.py` + `ai/summarizer.py`:
  PERFORMANCE/OBSERVATIONS/ACTIONS text; persisted to
  `financial_summaries` with unique `(kind,start,end)` dedupe;
  `regenerate=true` updates in place; metrics JSON-normalized before
  persistence (Decimal-safe — the pre-merge serialization bug is fixed and
  tested).
- **Frontend** — `/intelligence` staff page, four panels: analytics
  (KPIs, MRR/ARR + invoiced/collected charts, breakdowns, forecast),
  risks (summary cards, severity/category filters, per-risk AI
  explanation), copilot (chat, suggestions, sources/provider badges,
  loading/rate-limit errors), summaries (generate current-month/custom,
  dedupe behaviour, expandable reports, pagination). Linked from the
  finance dashboard; staff nav entry added.

### Integration & infra

- `contracts.py` typed DTOs + `integrations.py` DB-backed providers wired
  through `app/deps.py` — copilot consumes P2/P3 analytics through the
  contract, never re-implementing their domain logic.
- `financial_summaries` table + migration `0003_finance_intelligence`
  (chained on `0003_catalog_align`).
- Env/config: `AI_PROVIDER|AI_API_KEY|AI_MODEL|AI_TIMEOUT_S|AI_MAX_TOKENS|
  AI_RATE_LIMIT_PER_MINUTE` in `config.py`, `.env.example`, `render.yaml`.
- Docs: `PHASE2_PERSON4_ARCHITECTURE.md` (rules, safety, API surface).

## 2. Partial / interim (works, but flagged)

- **P2/P3 analytics providers** — `DbProductAnalyticsProvider` /
  `DbSubscriptionAnalyticsProvider` compute the contract DTOs from real
  shared tables until Persons 2/3 ship their own services. These are
  **interim implementations, not mocks** — swap the two `deps.py`
  factories when native services land; copilot unchanged.
- **`estimated_margin`** — computed only when `product.cost_price` is set;
  otherwise `None` (never fabricated).
- **`churned_last_30d`** — approximates closure time from
  `subscriptions.updated_at`; the schema has no status-change history.
  Noted on the DTO so the copilot/LLM can qualify it.
- **Historical MRR** — counts subscriptions whose `start_date`/`expiry_date`
  window covers `as_of` among subs active *today*; a mid-period pause is
  invisible. Documented on the module and in the architecture doc.
- **Rate limiting** — in-memory, per process; a multi-instance deployment
  needs a shared store to be strict.

## 3. Missing / not built

- **Real LLM calls in production paths** — implemented (OpenAI + Gemini
  providers) but untested against live APIs; default `AI_PROVIDER=none`
  runs the grounded template engine. Set key+provider to activate.
- **Downloadable report export** — summaries are viewable in-app and
  persisted; PDF/CSV export not implemented (Phase 1 has `reportlab`
  available if needed later).
- **P1 notification context** — reminder/email delivery status is not yet
  fed into collection analysis (contract point available in `deps.py`).

## 4. Tests

`backend/tests/` — all run with the LLM layer stubbed
(`TemplateProvider`/scripted/failing fakes); no real API calls.

| File | Covers |
|---|---|
| `finance_seed.py` | shared real-row seeding helpers |
| `test_finance_mrr.py` (7) | all four frequencies, excluded statuses, qty×price, plan breakdown, no double-count, trend start/expiry windowing |
| `test_finance_revenue.py` (6) | invoiced≠collected, draft/cancelled/voided exclusion, period-over-period growth, zero-previous → null, plan/product/customer/payment_method breakdowns |
| `test_finance_forecast.py` (6) | cycle amount incl. tax, inactive/out-of-horizon excluded, realized-rate weighting, billings≠collections, empty history → rate 0 |
| `test_finance_risk.py` (11) | each rule incl. threshold boundary, paid/cancelled exclusion, partial payments, voided-payment exclusion, severity scoring, record shape |
| `test_finance_copilot.py` (20) | intent table, grounded answers, invoiced≠collected, LLM wording wraps verified metrics, LLM failure → template fallback, injection stays data, question cap, broken P2 contract → declared unavailable, period resolution |
| `test_finance_summaries.py` (5) | persistence, dedupe, regenerate-in-place, defaults, period isolation |
| `test_finance_api.py` (9) | endpoint shapes, customer-role 403, 429 rate limit, risk explain, filters, summary lifecycle |

**`pytest tests/`: 164 passed** (includes merged P2/P3/Phase-1 tests).
`npm run typecheck` clean; `npm run build` succeeds.

## 5. AI provider configuration

| Var | Default | Notes |
|---|---|---|
| `AI_PROVIDER` | `none` | `none` → grounded template (offline-safe). `openai`/`gemini` + key enables LLM. |
| `AI_API_KEY` | — | required for real providers |
| `AI_MODEL` | `gpt-4o-mini` | e.g. `gemini-1.5-flash` |
| `AI_TIMEOUT_S` | `20` | per-call timeout |
| `AI_MAX_TOKENS` | `800` | output cap |
| `AI_RATE_LIMIT_PER_MINUTE` | `20` | per user, per process |

## 6. Deployment requirements

- `alembic upgrade head` runs `0003_finance_intelligence` after
  `0003_catalog_align`.
- `render.yaml` already declares the AI env vars (`AI_PROVIDER=none`
  default — no secrets needed to deploy; set `AI_API_KEY` in the dashboard
  to enable a real LLM).
- Auth: `AUTH_DEV_BYPASS=false` in prod → real JWT; endpoints require
  `admin`/`staff` role claims (P1 contract).

## 7. Known limitations

- Single-process rate limiter; no distributed limiting.
- No status-change history on subscriptions → historical MRR and churn
  timing are approximations (both documented on their DTOs/docstrings).
- Large-exposure rule uses a transparent capacity gauge (3× MRR or 90-day
  collections) — a heuristic, not a credit model.
- Product↔plan↔subscription relationships depend on the shared-schema
  IDs; invoice lines keep `product_id` as `int` (P2 catalog keeps int
  product PKs) while plan/subscription IDs are UUID — verified consistent
  post-merge.
- An in-flight `origin/main` merge existed during implementation; the
  UUID-based subscription schema and Phase-1 billing paths were preserved
  and the full suite passes on the merged tree. Per instructions, **no
  commit or push was performed** — all changes are in the working tree
  only, and the user's merge state was left untouched (conflict-free
  files, merge still open for the user to finalize).
