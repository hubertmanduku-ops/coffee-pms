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
   Log in and change the admin password (create a new admin user with a new password, then
   deactivate the seed account — there is no in-app password-change form yet; see "Known
   limitations").

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

## Known limitations / intentional simplifications
This system is deliberately scoped for operational tracking, not full ERP/accounting:
- No in-app "change my password" flow yet — an admin creates new users as needed.
- Farmer settlement is a worksheet/report, not an automated payment/ledger system.
- No Alembic migrations — schema is created via `Base.metadata.create_all` on startup, which is
  sufficient for this project's scope; introduce Alembic if the schema needs versioned changes
  later.
- Two warehouses and one wet mill are assumed fixed, per the stated business rules.
