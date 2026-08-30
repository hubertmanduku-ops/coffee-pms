# Coffee Pulping Management System (CPMS)

A simple, production-ready operational tracking system for a coffee wet mill: farmer records,
cherry intake, mixed-batch processing, inventory across two warehouses, expenses, sales,
reporting, and a dashboard — with role-based access control and audit logging.

Planning documents (BRD, Functional Requirements, DB Schema, User Stories, Wireframes,
Development Plan) are in `docs/01_PLANNING.md`.

## Tech stack

- Python 3.11, FastAPI
- Server-rendered Jinja2 templates + Bootstrap 5 (no separate frontend build)
- PostgreSQL (SQLAlchemy ORM)
- Deploys as a single service on Railway

## Project structure

```
app/
  main.py            FastAPI app, startup DB bootstrap, error handling
  config.py           Environment-driven settings
  database.py          SQLAlchemy engine/session
  models.py             ORM models (all tables)
  security.py            Password hashing + signed session tokens
  dependencies.py          Current-user + role-based access control
  audit.py                  Audit log writer
  utils.py                   Document numbering helper
  routers/                    One router per module (farmers, intake, batches, processing,
                               inventory, expenses, sales, reports, users, audit_log, dashboard, auth)
  templates/                    Jinja2 templates, one folder per module
  static/css/style.css           Small stylesheet on top of Bootstrap 5
docs/01_PLANNING.md               BRD / FR / schema / user stories / wireframes / dev plan
requirements.txt
Procfile, railway.json              Railway deployment config
.env.example
```

## Local setup

1. Create a PostgreSQL database (e.g. `createdb coffee_pms`).
2. Copy `.env.example` to `.env` and set `DATABASE_URL` and `SECRET_KEY`.
3. Install dependencies:

   ```
   pip install -r requirements.txt --break-system-packages
   ```

4. Run the app:

   ```
   uvicorn app.main:app --reload
   ```

5. Visit `http://localhost:8000`. On first run, the app creates all tables and seeds:
   - Admin user: **username `admin`, password `admin123`** — change this immediately.
   - Two warehouses: "Warehouse A" and "Warehouse B".

## Roles

- **admin** — everything, plus user management and the audit log.
- **manager** — all operational modules, reports, and financial summaries; no user management.
- **clerk** — day-to-day data entry (farmers, intake, batches, processing, inventory
  transactions, expenses, sales); cannot delete records or view financial-summary reports
  (expense/sales summaries, farmer settlement worksheet).

## Core workflow

1. Register farmers (`/farmers`).
2. Record cherry intake per delivery, choosing **purchase** or **processing-on-behalf**
   (`/intake`).
3. Open a batch and pull in one or more unassigned intakes — this is how mixed batches from
   multiple farmers are composed (`/batches`).
4. Log processing stages (pulping, fermentation, washing, soaking, drying, hulling/milling) and
   record outputs (parchment / green coffee) into a warehouse — this automatically posts an
   inventory-in transaction.
5. Manage stock: transfer between the two warehouses or make manual adjustments (`/inventory`).
6. Record expenses and sales; a sale automatically checks and deducts warehouse stock
   (`/expenses`, `/sales`).
7. Use `/reports` for intake summaries, batch yield/recovery, stock levels, expense/sales
   summaries, and a farmer settlement worksheet (purchase payables + an estimated
   processing-on-behalf output share, for manual finalization).

## Deploying to Railway

1. Push this project to a Git repository.
2. In Railway, create a new project → **Deploy from GitHub repo**.
3. Add a **PostgreSQL** plugin to the project — Railway will inject `DATABASE_URL`
   automatically.
4. Add an environment variable `SECRET_KEY` with a long random value.
5. Railway detects `railway.json`/`Procfile` and runs
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
6. On first request, the app creates tables and seeds the admin user and two warehouses.
   Log in and change the password via the user menu → **Change Password**.
7. **After any deploy that changed `app/models.py`** (schema change), also run the pending
   Alembic migration against the same `DATABASE_URL` — see "Database migrations" below. Railway
   does not run this automatically; the app will boot and serve fine either way (migrations here
   are written to be safe to run before or after a deploy), but features touching the new
   columns/tables will error until the migration has actually run.

## Progressive Web App (PWA)

CPMS is installable on desktop and mobile:

- `app/static/manifest.json` — app name, theme color, and icon set (regular + maskable
  variants, generated from `app/static/icons/`).
- `app/static/sw.js`, served at the root path `/sw.js` (not `/static/sw.js`) so its scope
  covers the whole app rather than just static assets. Strategy: pages always try the network
  first (so operational data is never stale) and only fall back to a cached offline page
  (`app/static/offline.html`) when there's no connectivity at all; static assets (CSS, icons)
  are cached-first.
- Once deployed over HTTPS (Railway does this by default), Chrome/Edge on desktop and Android
  will offer an install prompt automatically, and there's also an "Install App" item in the
  user menu (top right) once the browser signals the app is installable. iOS Safari: use the
  Share sheet → "Add to Home Screen".
- Bump `CACHE_VERSION` in `sw.js` whenever static assets change, so returning installed users
  get the update instead of a stale cached copy.

## Costing & Profitability

`/costing` gives a live cost/revenue/margin breakdown per batch (cherry cost and revenue always
come from actual recorded intake/sale amounts; operating cost is the sum of expenses actually
logged against the batch, falling back to a standard-rate estimate when none are logged yet).
`/costing/planner` is a what-if calculator — enter a cherry volume or a budget plus today's
cherry purchase price (never stored, since it varies season to season) to project output,
revenue, and profit, including a quick-reference table at the classic 10M–100M KES budget tiers.
Admins tune the underlying rate card (yield ratios, per-kg operating costs, selling price, FX,
and the cherry:parchment loss-ratio alarm band) at `/costing/settings`.

## Known limitations / intentional simplifications

This system is deliberately scoped for operational tracking, not full ERP/accounting:

- Farmer settlement (`/reports/farmer-settlement`) tracks "mark settled" status so amounts
  aren't re-listed once paid, but it's still a worksheet staff act on manually — there's no
  automated payment/ledger integration.
- Two warehouses and one wet mill are assumed fixed, per the stated business rules.

## Database migrations (Alembic)

Schema changes go through Alembic rather than relying solely on `create_all`. Every migration in
this repo is written to be **safe to run in any order relative to a deploy** — each step checks
whether its table/column already exists (since `Base.metadata.create_all()` at app startup may
have already created it) and skips if so — so there's no risky "run this before/after deploying"
sequencing to get right.

- Fresh databases: `Base.metadata.create_all()` still runs automatically at app startup and
  creates the full current schema — no manual migration step required to get started.
- After pulling changes that touch `app/models.py`, apply them to your database with:

  ```
  alembic upgrade head
  ```

  This works whether or not `alembic_version` exists yet on that database (e.g. the first time
  Alembic is run against the existing Railway production DB) — it just runs every migration in
  order, and each one no-ops for anything already present.
- When making your own schema change: edit `app/models.py`, then generate and review a migration:

  ```
  alembic revision --autogenerate -m "describe the change"
  alembic upgrade head
  ```

  Review the generated migration before applying — Postgres ENUM columns in particular need a
  manual `CREATE TYPE`/`DROP TYPE` step added for `add_column`/`drop_table` (see
  `alembic/versions/d954fd8ecc24_*.py` for a worked example, including the existence-check
  pattern used to make it safe to re-run).
