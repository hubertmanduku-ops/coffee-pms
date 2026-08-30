from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.audit import log_action
from app.database import get_db
from app.dependencies import ADMIN_ONLY, require_login, require_role

router = APIRouter(prefix="/costing", tags=["costing"])
templates = Jinja2Templates(directory="app/templates")

# Standard-cost tiers matching the original spreadsheet's budget scenarios (KES).
TIER_BUDGETS = [10_000_000, 20_000_000, 30_000_000, 50_000_000, 60_000_000, 80_000_000, 100_000_000]


def _get_rates(db: Session) -> models.CostRateSettings:
    return db.query(models.CostRateSettings).get(1)


def _project(cherry_kg: float, purchase_price_per_kg: float, rates: models.CostRateSettings) -> dict:
    """Reproduces the spreadsheet's chain: cherry -> parchment -> green coffee -> revenue,
    netting out the standard-rate opex to gross/net profit. Pulping is included as its own
    opex line (the source spreadsheet computed it but never added it into the total)."""
    parchment_kg = cherry_kg * float(rates.parchment_outturn_pct)
    green_kg = parchment_kg * float(rates.milling_recovery_pct)
    bags = green_kg / float(rates.bag_size_kg) if rates.bag_size_kg else 0
    revenue_usd = green_kg * float(rates.selling_price_usd_per_kg)
    revenue_kes = revenue_usd * float(rates.fx_rate_kes_per_usd)

    pulping_cost = cherry_kg * float(rates.pulping_cost_per_kg_cherry)
    milling_cost = cherry_kg * float(rates.milling_cost_per_kg_cherry)
    marketing_cost = green_kg * float(rates.marketing_cost_per_kg_green)
    bag_cost = bags * float(rates.bag_cost)
    transport_cost = green_kg * float(rates.transport_cost_per_kg_green)
    total_opex = pulping_cost + milling_cost + marketing_cost + bag_cost + transport_cost

    cherry_cost = cherry_kg * purchase_price_per_kg
    gross_profit = revenue_kes - total_opex
    net_profit = gross_profit - cherry_cost

    return {
        "cherry_kg": cherry_kg,
        "parchment_kg": parchment_kg,
        "green_kg": green_kg,
        "bags": bags,
        "revenue_usd": revenue_usd,
        "revenue_kes": revenue_kes,
        "pulping_cost": pulping_cost,
        "milling_cost": milling_cost,
        "marketing_cost": marketing_cost,
        "bag_cost": bag_cost,
        "transport_cost": transport_cost,
        "total_opex": total_opex,
        "cherry_cost": cherry_cost,
        "gross_profit": gross_profit,
        "net_profit": net_profit,
    }


def _batch_costing(db: Session, batch: models.Batch, rates: models.CostRateSettings) -> dict:
    cherry_kg = float(batch.total_cherry_kg or 0)
    parchment_kg = sum(float(o.quantity_kg) for o in batch.outputs if o.product_type.value == "parchment")
    green_kg = sum(float(o.quantity_kg) for o in batch.outputs if o.product_type.value == "green_coffee")
    recovery_pct = (green_kg / cherry_kg * 100) if cherry_kg else 0

    purchase_intakes = db.query(models.CoffeeIntake).filter(
        models.CoffeeIntake.batch_id == batch.id, models.CoffeeIntake.arrangement_type == models.ArrangementType.purchase
    )
    cherry_cost = sum(float(i.total_amount or 0) for i in purchase_intakes)

    actual_expenses = sum(float(e.amount) for e in db.query(models.Expense).filter(models.Expense.batch_id == batch.id))
    revenue = sum(float(s.total_amount) for s in db.query(models.Sale).filter(models.Sale.batch_id == batch.id))

    if actual_expenses:
        opex = actual_expenses
        opex_source = "actual"
    else:
        # No expenses logged against this batch yet — fall back to the standard-rate estimate
        # (pulping + milling on cherry kg, marketing + bags + transport on green coffee kg).
        opex = (
            cherry_kg * float(rates.pulping_cost_per_kg_cherry)
            + cherry_kg * float(rates.milling_cost_per_kg_cherry)
            + green_kg * float(rates.marketing_cost_per_kg_green)
            + (green_kg / float(rates.bag_size_kg) * float(rates.bag_cost) if rates.bag_size_kg else 0)
            + green_kg * float(rates.transport_cost_per_kg_green)
        )
        opex_source = "estimated"

    gross_profit = revenue - opex
    net_profit = gross_profit - cherry_cost
    cost_per_kg = ((cherry_cost + opex) / green_kg) if green_kg else None
    revenue_per_kg = (revenue / green_kg) if green_kg else None
    margin_per_kg = (net_profit / green_kg) if green_kg else None

    return {
        "batch": batch,
        "cherry_kg": cherry_kg,
        "parchment_kg": parchment_kg,
        "green_kg": green_kg,
        "recovery_pct": recovery_pct,
        "cherry_cost": cherry_cost,
        "opex": opex,
        "opex_source": opex_source,
        "revenue": revenue,
        "gross_profit": gross_profit,
        "net_profit": net_profit,
        "cost_per_kg": cost_per_kg,
        "revenue_per_kg": revenue_per_kg,
        "margin_per_kg": margin_per_kg,
    }


@router.get("")
def costing_home(
    request: Request,
    start: str = "",
    end: str = "",
    db: Session = Depends(get_db),
    user=Depends(require_login),
):
    start_date = start or (date.today() - timedelta(days=90)).isoformat()
    end_date = end or date.today().isoformat()
    rates = _get_rates(db)
    batches = (
        db.query(models.Batch)
        .filter(models.Batch.batch_date.between(start_date, end_date))
        .order_by(models.Batch.batch_date.desc())
        .all()
    )
    rows = [_batch_costing(db, b, rates) for b in batches]
    totals = {
        "cherry_cost": sum(r["cherry_cost"] for r in rows),
        "opex": sum(r["opex"] for r in rows),
        "revenue": sum(r["revenue"] for r in rows),
        "net_profit": sum(r["net_profit"] for r in rows),
        "green_kg": sum(r["green_kg"] for r in rows),
    }
    return templates.TemplateResponse(
        "costing/home.html",
        {"request": request, "user": user, "rows": rows, "totals": totals, "start": start_date, "end": end_date},
    )


@router.get("/planner")
def planner_form(request: Request, db: Session = Depends(get_db), user=Depends(require_login)):
    rates = _get_rates(db)
    last_intake = (
        db.query(models.CoffeeIntake)
        .filter(models.CoffeeIntake.arrangement_type == models.ArrangementType.purchase, models.CoffeeIntake.price_per_kg.isnot(None))
        .order_by(models.CoffeeIntake.intake_date.desc())
        .first()
    )
    suggested_price = float(last_intake.price_per_kg) if last_intake else None
    return templates.TemplateResponse(
        "costing/planner.html",
        {"request": request, "user": user, "rates": rates, "suggested_price": suggested_price, "result": None, "tiers": None},
    )


@router.post("/planner")
def planner_calculate(
    request: Request,
    purchase_price_per_kg: Decimal = Form(...),
    cherry_kg: str = Form(""),
    budget_kes: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require_login),
):
    rates = _get_rates(db)
    price = float(purchase_price_per_kg)
    if cherry_kg:
        kg = float(cherry_kg)
    elif budget_kes:
        kg = float(budget_kes) / price
    else:
        kg = 0

    result = _project(kg, price, rates) if kg else None
    tiers = [{"budget": b, **_project(b / price, price, rates)} for b in TIER_BUDGETS]

    return templates.TemplateResponse(
        "costing/planner.html",
        {
            "request": request, "user": user, "rates": rates, "suggested_price": price,
            "result": result, "tiers": tiers, "entered_price": price,
        },
    )


@router.get("/settings")
def settings_form(request: Request, db: Session = Depends(get_db), user=Depends(require_role(*ADMIN_ONLY))):
    rates = _get_rates(db)
    return templates.TemplateResponse("costing/settings.html", {"request": request, "user": user, "rates": rates})


@router.post("/settings")
def settings_update(
    parchment_outturn_pct: Decimal = Form(...),
    milling_recovery_pct: Decimal = Form(...),
    pulping_cost_per_kg_cherry: Decimal = Form(...),
    milling_cost_per_kg_cherry: Decimal = Form(...),
    marketing_cost_per_kg_green: Decimal = Form(...),
    bag_size_kg: Decimal = Form(...),
    bag_cost: Decimal = Form(...),
    transport_cost_per_kg_green: Decimal = Form(...),
    selling_price_usd_per_kg: Decimal = Form(...),
    fx_rate_kes_per_usd: Decimal = Form(...),
    loss_ratio_min: Decimal = Form(...),
    loss_ratio_max: Decimal = Form(...),
    db: Session = Depends(get_db),
    user=Depends(require_role(*ADMIN_ONLY)),
):
    rates = _get_rates(db)
    rates.parchment_outturn_pct = parchment_outturn_pct
    rates.milling_recovery_pct = milling_recovery_pct
    rates.pulping_cost_per_kg_cherry = pulping_cost_per_kg_cherry
    rates.milling_cost_per_kg_cherry = milling_cost_per_kg_cherry
    rates.marketing_cost_per_kg_green = marketing_cost_per_kg_green
    rates.bag_size_kg = bag_size_kg
    rates.bag_cost = bag_cost
    rates.transport_cost_per_kg_green = transport_cost_per_kg_green
    rates.selling_price_usd_per_kg = selling_price_usd_per_kg
    rates.fx_rate_kes_per_usd = fx_rate_kes_per_usd
    rates.loss_ratio_min = loss_ratio_min
    rates.loss_ratio_max = loss_ratio_max
    rates.updated_by = user.id
    db.commit()
    log_action(db, user, models.AuditAction.update, "cost_rate_settings", rates.id, "Updated standard cost rate card")
    return RedirectResponse("/costing/settings?success=Cost rates updated", status_code=303)
