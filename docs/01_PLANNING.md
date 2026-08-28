# Coffee Pulping Management System (CPMS)
## Planning Documentation

---

# 1. Business Requirements Document (BRD)

## 1.1 Background
The wet mill receives coffee cherry from farmers, processes it into green coffee (via pulping,
fermentation, washing and drying), stores intermediate and final products across two warehouses,
and sells green coffee. The mill operates two commercial models per farmer delivery:
- **Purchase**: the mill buys cherry outright from the farmer at a price per kg.
- **Processing-on-behalf**: the mill processes the farmer's cherry as a service; the farmer retains
  ownership of the resulting green coffee (less an agreed processing fee/loss), and the mill does not
  buy the cherry.

## 1.2 Objective
Provide a simple, reliable, web-based system for day-to-day operational tracking and data entry —
not a full ERP. The system must be easy to deploy (Railway), easy to maintain (single FastAPI app,
PostgreSQL), and usable by mill staff with minimal training.

## 1.3 Scope
In scope: Farmer management, coffee intake, batch management (including mixed batches from many
farmers/intakes), processing stage tracking, inventory across two warehouses, expenses, sales,
reporting, dashboard, role-based access, audit logging.

Out of scope (explicitly, to keep this simple): multi-mill support, payroll, accounting
double-entry ledger, mobile apps, offline sync, SMS/AI features, complex farmer settlement
automation (a manual/aided reconciliation report is provided instead — see 2.8).

## 1.4 Stakeholders
- Mill Manager — oversees operations, approves/reviews, views reports.
- Intake/Weighbridge Clerk — records cherry intake from farmers.
- Processing Operator — records pulping/fermentation/washing/drying stages and outputs.
- Store Keeper — manages warehouse stock movements.
- Accounts Clerk — records expenses and sales.
- Admin — manages users and system configuration.

## 1.5 Business Rules
1. **Mixed batch processing**: a processing batch can be composed of cherry from multiple intake
   records (multiple farmers), pooled and pulped together. The system tracks each farmer's/intake's
   contribution (kg) to a batch so that output can be apportioned later if needed.
2. **One wet mill**: all pulping happens at a single physical mill; no multi-site routing is needed.
3. **Two warehouses**: fixed at two warehouse records (e.g. "Warehouse A" / "Warehouse B"), used to
   store parchment/green coffee/cherry stock; stock movements are tracked per warehouse.
4. **Green coffee is the final product**: the processing pipeline ends when green coffee is produced
   and put into inventory; that is what is sold.
5. **Internal milling**: hulling/milling of parchment into green coffee is done in-house and modeled
   as a processing stage, not an external service.
6. **Purchase vs. processing-on-behalf** must be recorded per intake and drives farmer settlement:
   purchased cherry has a price/kg and generates a payable to the farmer; processing-on-behalf cherry
   has no purchase price and instead entitles the farmer to a share of output (tracked via the
   batch-intake composition table and a reconciliation report).

## 1.6 Success Criteria
- All cherry intake, batch composition, processing stages, and outputs are recorded and traceable
  end-to-end (farmer → intake → batch → output → inventory → sale).
- Two warehouses' stock balances are always derivable from recorded transactions.
- Expenses and sales are recorded and summarized for a given period.
- Role-based access prevents unauthorized data entry/deletion.
- Every create/update/delete of significant records is captured in an audit log.

---

# 2. Functional Requirements

## 2.1 Authentication & RBAC
- FR-1: Users log in with username/password (session cookie).
- FR-2: Roles: `admin`, `manager`, `clerk`.
  - `admin`: everything, incl. user management and warehouse/config setup.
  - `manager`: all operational modules + reports; cannot manage users.
  - `clerk`: create/edit operational records (farmers, intake, batches, processing, inventory
    transactions, expenses, sales); cannot delete records or view financial-summary reports.
- FR-3: Every page/route enforces role checks server-side (not just hidden UI).

## 2.2 Farmer Management
- FR-4: CRUD for farmers: code, name, phone, national ID, location, default arrangement type,
  bank/mobile-money account, active flag.
- FR-5: Farmer detail page shows intake history and running totals (kg delivered, amount payable).

## 2.3 Coffee Intake Management
- FR-6: Record intake: farmer, date, cherry quantity (kg), arrangement type (purchase / processing
  on behalf), price/kg (purchase only), quality notes, moisture %, recorded-by.
- FR-7: System auto-computes total amount payable for purchase intakes.
- FR-8: Intakes start as "unassigned" until linked to a batch.
- FR-9: Intake list filterable by farmer, date range, arrangement type, batch-assigned status.

## 2.4 Batch Management
- FR-10: Create a batch (batch number auto-generated, date, notes).
- FR-11: Add one or more unassigned intakes to a batch (mixed batch); system sums total cherry kg
  and tracks each intake's kg contribution (`batch_intakes`).
- FR-12: Batch has a status: `open` → `processing` → `completed`.
- FR-13: Batch detail page shows composition (farmers & kg), processing stages, and outputs.

## 2.5 Processing Tracking
- FR-14: Record processing stages against a batch: Pulping, Fermentation, Washing, Soaking,
  Drying, Hulling/Milling — each with start/end datetime, operator, and free-text parameters/notes.
- FR-15: Record processing output(s): parchment kg and/or green coffee kg, moisture %, destination
  warehouse; posts an inventory-in transaction automatically.
- FR-16: Completing a "Hulling/Milling" stage + output marks the batch eligible for `completed`.

## 2.6 Inventory Management
- FR-17: Two warehouse records fixed in config; each holds stock by product type (cherry, parchment,
  green coffee).
- FR-18: All stock changes go through `inventory_transactions` (in / out / transfer / adjustment),
  each referencing its source (processing output, sale, manual adjustment, inter-warehouse transfer).
- FR-19: Current stock per warehouse/product = sum of transactions (computed, not stored redundantly
  — stored balance is a cached convenience field updated transactionally).
- FR-20: Inter-warehouse transfer creates a linked pair (out of A, in of B).

## 2.7 Expense Management
- FR-21: Record expenses: date, category (e.g. labor, fuel, transport, maintenance, utilities,
  other), amount, description, optional link to a batch or warehouse.
- FR-22: List/filter by date range and category; totals by category.

## 2.8 Sales Management
- FR-23: Record a sale: date, customer, product type (parchment/green coffee), quantity, unit
  price, warehouse (source of stock), optional batch link; posts an inventory-out transaction.
- FR-24: Prevent sale quantity exceeding available warehouse stock for that product.
- FR-25: Sales list/filter by date range, customer, product; revenue totals.

## 2.9 Reporting & Dashboard
- FR-26: Dashboard: today/this-week intake kg, open batches, stock-on-hand by warehouse/product,
  this-month expenses total, this-month sales revenue, recent activity feed.
- FR-27: Reports: Intake summary (by farmer/date range), Batch yield report (input kg → output kg,
  recovery %), Inventory stock report (by warehouse), Expense summary (by category/period), Sales
  summary (by period/product), Farmer settlement worksheet (purchase payables + processing-on-behalf
  output share based on batch composition ratios) for manual finalization.

## 2.10 Audit Logging
- FR-28: Every create/update/delete on farmers, intakes, batches, processing records, inventory
  transactions, expenses, sales, and user accounts writes an `audit_logs` row: who, when, what
  action, entity type/id, and a short JSON/text diff or description.
- FR-29: Admin-only audit log viewer, filterable by user/entity/date.

---

# 3. Database Schema (PostgreSQL)

```
users(id PK, username UNIQUE, password_hash, full_name, role, is_active, created_at)

warehouses(id PK, name UNIQUE, location, is_active)

farmers(id PK, farmer_code UNIQUE, full_name, phone, national_id, location,
        default_arrangement, bank_account, is_active, created_at)

coffee_intakes(id PK, intake_number UNIQUE, farmer_id FK->farmers, intake_date,
        quantity_kg, arrangement_type[purchase|processing_on_behalf],
        price_per_kg NULLABLE, total_amount NULLABLE, quality_grade, moisture_content,
        batch_id FK->batches NULLABLE, recorded_by FK->users, created_at)

batches(id PK, batch_number UNIQUE, batch_date, status[open|processing|completed],
        total_cherry_kg, notes, created_by FK->users, created_at)

batch_intakes(id PK, batch_id FK->batches, intake_id FK->coffee_intakes UNIQUE,
        quantity_kg)   -- composition / mixed-batch traceability

processing_stages(id PK, batch_id FK->batches,
        stage[pulping|fermentation|washing|soaking|drying|hulling_milling],
        start_datetime, end_datetime NULLABLE, parameters TEXT, notes TEXT,
        recorded_by FK->users, created_at)

processing_outputs(id PK, batch_id FK->batches, output_date,
        product_type[parchment|green_coffee], quantity_kg, moisture_content,
        warehouse_id FK->warehouses, recorded_by FK->users, created_at)

inventory_transactions(id PK, warehouse_id FK->warehouses,
        product_type[cherry|parchment|green_coffee],
        transaction_type[in|out|transfer_in|transfer_out|adjustment],
        quantity_kg, reference_type, reference_id, transaction_date,
        recorded_by FK->users, notes, created_at)

warehouse_stock(id PK, warehouse_id FK->warehouses, product_type,
        quantity_kg, UNIQUE(warehouse_id, product_type))   -- cached running balance

expenses(id PK, expense_date, category, description, amount,
        batch_id FK->batches NULLABLE, warehouse_id FK->warehouses NULLABLE,
        recorded_by FK->users, created_at)

sales(id PK, sale_number UNIQUE, sale_date, customer_name,
        product_type[parchment|green_coffee], quantity_kg, unit_price, total_amount,
        warehouse_id FK->warehouses, batch_id FK->batches NULLABLE,
        recorded_by FK->users, created_at)

audit_logs(id PK, user_id FK->users, username, action[create|update|delete|login],
        entity_type, entity_id, description, created_at)
```

Relationships: farmer 1—N intakes; batch 1—N intakes (via batch_intakes, mixed batch);
batch 1—N processing_stages; batch 1—N processing_outputs; processing_output → inventory_transaction
(in); sale → inventory_transaction (out); warehouse 1—N stock rows (one per product_type).

---

# 4. User Stories

- As an **Admin**, I can create user accounts and assign roles so staff can log in with
  appropriate access.
- As a **Clerk**, I can register a new farmer with their contact and payment details.
- As a **Weighbridge Clerk**, I can record a cherry intake for a farmer, choosing purchase or
  processing-on-behalf, so the delivery is captured with weight and price.
- As a **Manager**, I can open a batch and pull in several unassigned intakes (possibly from
  different farmers) into one mixed batch so pulping can start.
- As a **Processing Operator**, I can log the start/end of pulping, fermentation, washing, and
  drying stages for a batch so the process is traceable.
- As a **Processing Operator**, I can record the parchment/green coffee output of a batch into a
  chosen warehouse so inventory reflects what was produced.
- As a **Store Keeper**, I can transfer stock between the two warehouses and see current balances.
- As an **Accounts Clerk**, I can log an expense against a category (and optionally a batch) so
  costs are tracked.
- As an **Accounts Clerk**, I can record a sale of green coffee from a warehouse and the system
  prevents me from selling more than what's in stock.
- As a **Manager**, I can view a dashboard summarizing today's intake, open batches, stock levels,
  and this month's expenses/sales.
- As a **Manager**, I can generate a batch yield report to see input cherry kg vs. output green
  coffee kg (recovery %).
- As a **Manager**, I can view a farmer settlement worksheet showing amounts payable for purchased
  cherry and output share for processing-on-behalf cherry.
- As an **Admin**, I can view an audit log of who changed what and when.

---

# 5. Wireframes (textual layout)

```
[Top Navbar]  CPMS | Dashboard | Farmers | Intake | Batches | Processing | Inventory |
              Expenses | Sales | Reports | (admin: Users | Audit Log)      [user ▾ Logout]

--- Dashboard ---
+-----------------------------------------------------------+
| Cards: Today's Intake (kg) | Open Batches | This Month     |
|        Stock: Wh A / Wh B by product | Expenses | Sales    |
+-----------------------------------------------------------+
| Recent Activity (last 10 audit events)                    |
+-----------------------------------------------------------+

--- List pages (Farmers/Intake/Batches/etc.) ---
+-----------------------------------------------------------+
| [Filter bar: date range / farmer / status]   [+ New]      |
+-----------------------------------------------------------+
| Table: sortable columns, row click -> detail, Edit/Delete  |
+-----------------------------------------------------------+
| Pagination                                                 |
+-----------------------------------------------------------+

--- Form pages (New/Edit) ---
+-----------------------------------------------------------+
| Card with labeled Bootstrap form fields, validation        |
| [Save] [Cancel]                                            |
+-----------------------------------------------------------+

--- Batch Detail ---
+-----------------------------------------------------------+
| Batch #, date, status badge                                 |
| Composition table: Farmer | Intake # | kg  [+ Add intake]  |
| Processing stages timeline table  [+ Add stage]             |
| Outputs table (product, kg, warehouse) [+ Add output]       |
| Yield: total in kg / total out kg / recovery %              |
+-----------------------------------------------------------+

--- Inventory ---
+-----------------------------------------------------------+
| Stock summary cards per warehouse x product                 |
| Transactions table with filters  [+ Transfer] [+ Adjust]    |
+-----------------------------------------------------------+
```

---

# 6. Development Plan

| Phase | Deliverable | Notes |
|---|---|---|
| 0 | Project scaffold, config, DB models, auth, RBAC, audit helper, base template | Foundation |
| 1 | Farmer management module | CRUD + list/detail |
| 2 | Coffee intake module | CRUD, farmer totals |
| 3 | Batch management + mixed-batch composition | Add/remove intakes to batch |
| 4 | Processing tracking (stages + outputs) | Posts inventory-in |
| 5 | Inventory (warehouses, transactions, transfers, stock report) | |
| 6 | Expense management | |
| 7 | Sales management | Stock validation, posts inventory-out |
| 8 | Reporting module + Dashboard | Aggregation queries |
| 9 | User management + Audit log viewer (admin) | |
| 10 | Polish: seed script, README, Railway deploy config | |

Deployment: single FastAPI service on Railway, PostgreSQL plugin, `DATABASE_URL` env var,
`Procfile`/`railway.json` with `uvicorn app.main:app`, startup event creates tables if absent
(simple `Base.metadata.create_all` — sufficient for this scope; Alembic can be added later).
