# Brightloop Frontend — UI/UX Implementation Notes

Design system: **Sage Green + Cream + Black typography**, Inter font, minimal SaaS aesthetic.

## Design tokens (`frontend/tailwind.config.js`)

| Token | Hex | Use |
|---|---|---|
| `sage` | `#A3B18A` | primary brand accent, buttons |
| `sage-deep` | `#718267` | hover/active accent, links |
| `sage-soft` | `#E5EBDD` | active nav, selected states |
| `sage-faint` | `#EFF2E7` | skeletons, subtle hover |
| `cream` | `#F6F4EA` | page background |
| `cream-card` | `#FFFEF8` | card surfaces |
| `ink` | `#171A16` | primary text |
| `ink-muted` | `#62665F` | secondary text |
| `line` | `#DFE2D7` | borders |
| `success`/`warning`/`danger` | `#527A55`/`#A47B36`/`#AD5750` | semantic only |

## Structure

- `src/components/AppShell.tsx` — fixed sidebar (grouped, role-aware), mobile drawer, topbar, user section + logout.
- `src/components/ui/` — primitives (`button`, `card`, `input`, `select`, `label`, `table`, `badge`) + `extras.tsx` (`PageHeader`, `StatCard`, `Empty`, `Skeleton`/`TableSkeleton`, `Spinner`, `Modal`, `ConfirmDialog`) + `toast.tsx` (toast provider + `useToast`).
- `src/lib/auth.ts` — token storage, login/register/reset helpers, `me`, `logout` (redirects to `/login`).

## Routes

| Path | Page | Access |
|---|---|---|
| `/login` `/register` `/forgot-password` `/reset-password` | auth | public |
| `/` | finance dashboard (KPIs, revenue chart, overdue table) | staff/admin |
| `/customers` `/staff` | user management (`/staff` admin-only nav) | staff/admin |
| `/products` `/plans` `/taxes` `/discounts` | catalog admin | staff/admin |
| `/quotations` `/quotations/:id` | quotation list/detail + send/confirm/convert | staff/admin |
| `/subscriptions` | list + lifecycle modal (pause/resume/renew/close) | staff/admin |
| `/invoices` `/invoices/:id` | invoice management | staff/admin |
| `/payments` `/billing` `/reports` | finance ops | staff/admin |
| `/intelligence/{analytics,copilot,risks,summaries}` | finance-intelligence panels | staff/admin |
| `/notifications` `/settings` | system | all signed-in |
| `/portal` `/portal/invoices` `/portal/invoices/:id` `/portal/payments` | customer portal | customer only |

Customers never see staff navigation or routes (`StaffOnly`/`CustomerOnly` guards + server-side RBAC remain the real boundary).

## Verified

- `npm run build` (`tsc --noEmit && vite build`) — clean.
- All API paths used by pages verified against the running backend (fresh `alembic upgrade head` through `0003_finance_intelligence`).

## Remaining limitations

- **Notifications**: the backend has no notification-center/preferences API; the page shows recent invoice + billing-run activity. Email delivery timestamps live on invoice detail only (not list responses).
- **Quotation line editing**: line items come from templates or API calls; the UI does not yet offer an inline line editor (create quotation with a template, or add lines via `/docs`).
- **Product variants**: managed via `/products/{id}/variants` API; no dedicated variants UI yet.
- **Settings**: read-only profile + reset-password link; no in-app change-password or preference persistence (no backend endpoints).
- **Bundle size**: single chunk ~830 kB (Recharts + router + query). Code-splitting with dynamic imports is a future optimization, not a blocker.
