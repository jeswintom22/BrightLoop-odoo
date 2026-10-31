# Phase 2 — Person 4: Revenue Intelligence & AI Finance Copilot

Status: implemented (see `PHASE2_PERSON4_IMPLEMENTATION_REPORT.md` for what is
real vs interim). Extends Phase 1 billing — no Phase 1 tables, services or
endpoints were replaced.

Design order, per the brief: **financial correctness → deterministic
analytics → AI interpretation**. The LLM never calculates, never sees the
database, and can be removed entirely without losing a single number —
every AI feature degrades to a grounded template.

---

## 1. Module layout

```
backend/app/modules/finance_intelligence/
├── router.py            # /api/v1/finance-intelligence/* — admin/staff only
├── schemas.py           # Pydantic v2 DTOs (Decimal → float on the wire only)
├── service.py           # summary orchestration: dedupe, persist, regenerate
├── models.py            # financial_summaries (only persisted AI artifact)
├── contracts.py         # P2/P3 analytics DTOs + Protocols
├── integrations.py      # interim DB-backed providers for those contracts
├── analytics/
│   ├── mrr_arr.py       # normalized recurring revenue
│   ├── revenue.py       # invoiced-vs-collected trends, growth, breakdowns
│   ├── forecasting.py   # expected billings vs expected collections
│   ├── risk_detection.py# 5 deterministic risk rules + severity scoring
│   └── reports.py       # performance report assembly (feeds summaries)
└── ai/
    ├── provider.py      # LLMProvider protocol + openai/gemini/template + rate limiter
    ├── prompts.py       # grounding + injection-containment system prompts
    ├── copilot.py       # intent → metrics gather → LLM prose
    ├── risk_explainer.py# risk record → plain-language explanation
    └── summarizer.py    # metrics JSON → PERFORMANCE/OBSERVATIONS/ACTIONS
```

Frontend: `frontend/src/features/finance-intelligence/` — one page
(`/intelligence`, staff nav) with four panels:
`revenue-analytics/`, `risk-analysis/`, `copilot/`, `financial-summaries/`.

---

## 2. Financial definitions (fixed rules)

### MRR / ARR (`analytics/mrr_arr.py`)

- Eligible: `subscriptions.status = 'active'` **only**. paused / closed /
  draft / confirmed contribute nothing while inactive.
- Recurring amount per subscription = `Σ items(quantity × unit_price)`,
  **pre-tax** (tax is a pass-through liability, not revenue). One-time
  charges can't enter MRR because only recurring subscription lines are read.
- Frequency normalization to a monthly basis:
  `daily × 365/12 · weekly × 52/12 · monthly × 1 · yearly ÷ 12`.
- `ARR = MRR × 12` — contract value, never cash collected.
- MRR is **never** derived from invoice totals. Invoiced/collected revenue
  are separate metrics (§3).
- Point-in-time MRR (`as_of`): subscription counted when
  `start_date ≤ as_of` and (`expiry_date IS NULL` or `expiry_date > as_of`),
  restricted to subs active *today*. Subscriptions carry no status-change
  history, so historical MRR approximates past status — documented
  limitation, not hidden.

### Invoiced vs collected (`analytics/revenue.py`)

- `invoiced` = Σ `invoices.total_amount` where status ∈ `confirmed|paid`,
  bucketed by `issue_date`. Draft/cancelled excluded.
- `collected` = Σ `payments.amount` where status = `posted`, bucketed by
  `paid_at`. Voided payments excluded.
- Growth % = `(current − previous)/previous × 100`; `null` when previous = 0
  (never a misleading infinite/zero percentage). Previous period = same
  length window ending the day before `from`.
- Buckets: `day|week|month|year` — `strftime` on SQLite, `date_trunc` on
  Postgres.

### Breakdowns

`plan`/`customer`/`period` → invoiced total; `product` → Σ invoice-line
`line_total`; `payment_method` → cash actually collected. All respect the
same status filters.

### Collection forecast (`analytics/forecasting.py`)

Two clearly-separated figures — a heuristic, explicitly not ML:

- `expected_billings`: active subscriptions with `next_billing_date` inside
  the horizon (and not expired before it), valued per cycle at
  `Σ qty × unit_price × (1 + tax_rate/100)` — tax-inclusive because that's
  what the billing engine will invoice.
- `expected_collections`: outstanding on confirmed invoices due inside the
  horizon × realized collection rate `= collected(90d)/invoiced(90d)`
  clamped to `[0,1]`.
- `expected_total_cash_in` = collections + billings × rate.

### Risk detection (`analytics/risk_detection.py`)

Five deterministic rules; no LLM anywhere in detection:

| Category              | Rule |
|-----------------------|------|
| `high_value_overdue`  | confirmed invoice past due, outstanding ≥ ₹10,000 |
| `multiple_overdue`    | ≥ 2 currently-overdue invoices per customer |
| `repeated_late_payments` | ≥ 2 posted payments settling after due date |
| `renewal_unpaid`      | active subscription billing ≤ 30 days while customer has overdue invoices |
| `large_exposure`      | outstanding > max(3× customer MRR, 90-day collections) — exposure beyond demonstrated payment capacity |

Severity score: points from days-overdue bands, amount-vs-threshold bands,
overdue count → `high ≥ 4`, `medium ≥ 2`, else `low`. Paid/cancelled
invoices and voided payments never produce risks. Each record carries
customer/subscription/invoice refs, amounts, reason and recommended action.

### Performance reports (`analytics/reports.py`)

`GET /reports/performance` assembles period totals (invoiced, collected,
invoice count, outstanding, overdue), previous-period comparison, growth %,
collection rate, MRR/ARR snapshot and plan-revenue breakdown. This is also
the metrics payload persisted inside `financial_summaries`.

---

## 3. AI layer

### Provider abstraction (`ai/provider.py`)

`build_provider(settings)` selects on `AI_PROVIDER`:

- `openai` → `POST /v1/chat/completions` (httpx, `AI_API_KEY`, `AI_MODEL`)
- `gemini` → `POST /v1beta/models/{model}:generateContent`
- `none` / missing key / unknown → `TemplateProvider`

`TemplateProvider` is **not** an LLM — responses are tagged
`provider='template'` (or `template-fallback` after an `LLMError`), and the
UI displays that badge. Template text is assembled from the same verified
metrics, so answers stay grounded even offline. `AI_TIMEOUT_S` bounds every
provider call; failures raise `LLMError` and degrade rather than 500.

A per-user sliding-window `RateLimiter` (`AI_RATE_LIMIT_PER_MINUTE`, per
process) guards copilot/explain/generate — returns `429 RATE_LIMITED`.
In-memory; horizontal scaling weakens it (documented limitation).

### Copilot flow (`ai/copilot.py`)

1. `classify(question)` — keyword rules, no LLM. Unknown → capability list.
2. `resolve_period(question)` — "this month/last month/this quarter/…" →
   concrete dates (default: current month).
3. `_gather(intent, …)` — runs the mapped analytics function(s); P2/P3
   contract providers join when the intent needs them. Provider exceptions
   surface as `available: false` inside metrics — never fabricated.
4. `llm.generate(system=COPILOT_SYSTEM, user=<question,metrics,ranges>)` —
   the LLM only words the answer.
5. LLM failure/template mode → grounded `_template_answer` (same numbers).

### Safety properties

- No SQL generation, no DB access for the model — predefined parameterized
  analytics only.
- System prompt declares the question a `<user_question>` **data block**;
  embedded directives ("ignore your rules", "run SQL") are defined as data
  to ignore. Injection cannot reach data.
- Every figure the model can state comes from the supplied metrics JSON;
  prompts forbid inventing/estimating, require stating the date range, and
  require declaring missing data rather than guessing.
- Roles: every endpoint is `require_roles("admin","staff")` — customer
  tokens get 403. The AI layer inherits this; it cannot widen access.
- No writes: copilot/explain/summarize never mutate invoices, payments or
  subscriptions. Summaries persist only report text + metrics snapshot.
- No secrets in prompts; only aggregated metrics and display names are
  sent. Questions are capped at 1000 chars.

### Risk explanations (`ai/risk_explainer.py`)

`POST /risks/explain` accepts `risk_index` (from `GET /risks`) or an inline
record — the frontend posts the record itself so re-detection can't race.
LLM rewrites the record's own facts into plain language; on any failure the
deterministic template (assembled from the record's fields) is returned.

### Financial summaries (`service.py` + `ai/summarizer.py`)

- `POST /summaries/generate` computes `performance_report` metrics, renders
  PERFORMANCE/OBSERVATIONS/ACTIONS text, persists to `financial_summaries`.
- Unique constraint `(period_kind, period_start, period_end)` — duplicate
  generate calls return the stored report unless `regenerate=true`, which
  updates in place. Provenance (`provider`, `model`, `generated_by`,
  `created_at`) is auditable.
- Metrics are normalized to JSON-safe types before persistence (`Decimal`
  → `float`) — the DB columns remain the numeric source of truth; the JSON
  blob is informational.

---

## 4. P2 / P3 integration contracts (`contracts.py`)

In-process service contracts (no HTTP inside the monolith):

- `ProductAnalyticsProvider.product_analytics(session) -> ProductAnalytics`
  — `top_products_by_revenue`, `top_products_by_margin`,
  `most_popular_plans`, `underperforming_plans`, `available`, `note`.
- `SubscriptionAnalyticsProvider.subscription_analytics(session) -> …`
  — active/paused/closed counts, `churned_last_30d` (proxy: `updated_at`
  within 30d — no status history exists), `renewals_due_30d`,
  `expiring_30d`, `upcoming_renewals[]`.

**Interim implementations** (`integrations.py`) compute these DTOs from the
shared tables — real records, not mocks. When P2/P3 ship native services,
swap the two factories in `app/deps.py`
(`get_product_analytics_provider` / `get_subscription_analytics_provider`);
the copilot is unchanged. Known contract limitations: `estimated_margin`
uses `product.cost_price` when set else `None` (profitability is never
fabricated); churn timing is approximate (noted on the DTO).

Cross-model note: P2 catalog PKs are now UUID (`subscription_plans.id`,
`tax_configurations.id`, `discounts.id`) after `0003_catalog_align`; P3
subscriptions use UUID PKs matching billing's `invoices.subscription_id`
column. Billing cross-module columns intentionally keep no DB-level FK
(architecture doc §7).

---

## 5. API surface

All under `/api/v1/finance-intelligence`, all `admin|staff` only:

| Endpoint | Purpose |
|---|---|
| `GET /revenue/mrr` `?as_of` | snapshot: MRR, ARR, by-plan, by-frequency |
| `GET /revenue/arr` | same snapshot (ARR derived, not separate logic) |
| `GET /revenue/mrr-trend?from&to` | month-end MRR/ARR points |
| `GET /revenue/trends?interval&from&to` | invoiced vs collected + growth |
| `GET /revenue/breakdown?by&from&to&limit` | plan/product/customer/period/payment_method |
| `GET /revenue/forecast?horizon_days` | expected billings vs collections |
| `GET /reports/performance?from&to` | full performance report |
| `GET /risks?severity&category` | risk records + aggregate summary |
| `GET /risks/summary` | aggregate only |
| `POST /risks/explain` `{risk_index|risk}` | AI explanation (rate-limited) |
| `POST /copilot` `{question}` | natural-language finance Q&A (rate-limited) |
| `GET /summaries?page&page_size` | generated reports, newest first |
| `POST /summaries/generate` | create/dedupe/regenerate (rate-limited) |
| `GET /summaries/{id}` | one report |

## 6. Persistence & migrations

`0003_finance_intelligence` (down_revision `0003_catalog_align`) creates
`financial_summaries` — the **only** table this module adds. Analytics are
computed on demand against existing billing/subscription/catalog tables;
no cached-metric tables, no denormalization to keep in sync.

## 7. Environment variables

See `backend/.env.example` and `render.yaml`: `AI_PROVIDER`,
`AI_API_KEY`, `AI_MODEL`, `AI_TIMEOUT_S`, `AI_MAX_TOKENS`,
`AI_RATE_LIMIT_PER_MINUTE`. Defaults run fully offline (`none` + template).
