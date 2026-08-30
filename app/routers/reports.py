from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.audit import log_action
from app.database import get_db
from app.dependencies import CAN_VIEW_FINANCIALS, require_login, require_role

router = APIRouter(prefix="/reports", tags=["reports"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def reports_home(request: Request, user=Depends(require_login)):
    return templates.TemplateResponse("reports/home.html", {"request": request, "user": user})


@router.get("/intake-summary")
def intake_summary(
    request: Request,
    start: str = "",
    end: str = "",
    db: Session = Depends(get_db),
    user=Depends(require_login),
):
    start_date = start or (date.today() - timedelta(days=30)).isoformat()
    end_date = end or date.today().isoformat()
    rows = (
        db.query(
            models.Farmer.full_name,
            func.count(models.CoffeeIntake.id),
            func.sum(models.CoffeeIntake.quantity_kg),
            func.sum(models.CoffeeIntake.total_amount),
        )
        .join(models.CoffeeIntake, models.CoffeeIntake.farmer_id == models.Farmer.id)
        .filter(models.CoffeeIntake.intake_date.between(start_date, end_date))
        .group_by(models.Farmer.full_name)
        .order_by(models.Farmer.full_name)
        .all()
    )
    return templates.TemplateResponse(
        "reports/intake_summary.html",
        {"request": request, "user": user, "rows": rows, "start": start_date, "end": end_date},
    )


@router.get("/batch-yield")
def batch_yield(request: Request, db: Session = Depends(get_db), user=Depends(require_login)):
    batches = db.query(models.Batch).order_by(models.Batch.batch_date.desc()).all()
    rates = db.query(models.CostRateSettings).get(1)
    data = []
    for b in batches:
        total_out = sum(float(o.quantity_kg) for o in b.outputs)
        recovery = (total_out / float(b.total_cherry_kg) * 100) if b.total_cherry_kg else 0
        parchment_kg = sum(float(o.quantity_kg) for o in b.outputs if o.product_type.value == "parchment")
        loss_ratio = (float(b.total_cherry_kg) / parchment_kg) if b.total_cherry_kg and parchment_kg else None
        loss_ratio_ok = (
            rates is not None and loss_ratio is not None
            and float(rates.loss_ratio_min) <= loss_ratio <= float(rates.loss_ratio_max)
        )
        data.append(
            {"batch": b, "total_out": total_out, "recovery": recovery, "loss_ratio": loss_ratio, "loss_ratio_ok": loss_ratio_ok}
        )
    return templates.TemplateResponse("reports/batch_yield.html", {"request": request, "user": user, "data": data, "rates": rates})


@router.get("/inventory-stock")
def inventory_stock(request: Request, db: Session = Depends(get_db), user=Depends(require_login)):
    stock = db.query(models.WarehouseStock).all()
    return templates.TemplateResponse("reports/inventory_stock.html", {"request": request, "user": user, "stock": stock})


@router.get("/expense-summary")
def expense_summary(
    request: Request,
    start: str = "",
    end: str = "",
    db: Session = Depends(get_db),
    user=Depends(require_role(*CAN_VIEW_FINANCIALS)),
):
    start_date = start or (date.today() - timedelta(days=30)).isoformat()
    end_date = end or date.today().isoformat()
    rows = (
        db.query(models.Expense.category, func.sum(models.Expense.amount))
        .filter(models.Expense.expense_date.between(start_date, end_date))
        .group_by(models.Expense.category)
        .all()
    )
    total = sum(float(r[1]) for r in rows)
    return templates.TemplateResponse(
        "reports/expense_summary.html",
        {"request": request, "user": user, "rows": rows, "total": total, "start": start_date, "end": end_date},
    )


@router.get("/sales-summary")
def sales_summary(
    request: Request,
    start: str = "",
    end: str = "",
    db: Session = Depends(get_db),
    user=Depends(require_role(*CAN_VIEW_FINANCIALS)),
):
    start_date = start or (date.today() - timedelta(days=30)).isoformat()
    end_date = end or date.today().isoformat()
    rows = (
        db.query(models.Sale.product_type, func.sum(models.Sale.quantity_kg), func.sum(models.Sale.total_amount))
        .filter(models.Sale.sale_date.between(start_date, end_date))
        .group_by(models.Sale.product_type)
        .all()
    )
    total = sum(float(r[2]) for r in rows)
    return templates.TemplateResponse(
        "reports/sales_summary.html",
        {"request": request, "user": user, "rows": rows, "total": total, "start": start_date, "end": end_date},
    )


def _compute_farmer_settlement(db: Session, farmer: models.Farmer):
    """Payable/output-share for a farmer's *unsettled* intakes only — intakes already covered by
    a prior `paid` FarmerSettlement (by date) are excluded so the worksheet doesn't re-list them."""
    last_settlement = (
        db.query(models.FarmerSettlement)
        .filter(models.FarmerSettlement.farmer_id == farmer.id, models.FarmerSettlement.status == models.SettlementStatus.paid)
        .order_by(models.FarmerSettlement.as_of_date.desc())
        .first()
    )
    last_date = last_settlement.as_of_date if last_settlement else None

    intakes = [i for i in farmer.intakes if not last_date or i.intake_date > last_date]
    purchase_intakes = [i for i in intakes if i.arrangement_type.value == "purchase"]
    pob_intakes = [i for i in intakes if i.arrangement_type.value == "processing_on_behalf"]
    payable = sum(float(i.total_amount or 0) for i in purchase_intakes)
    pob_kg = sum(float(i.quantity_kg) for i in pob_intakes)
    # Output share estimate: for each processing-on-behalf intake, apportion the batch's
    # total green-coffee output by this intake's share of the batch's total cherry kg.
    output_share_kg = 0.0
    for i in pob_intakes:
        if not i.batch or not i.batch.total_cherry_kg:
            continue
        batch_output = sum(float(o.quantity_kg) for o in i.batch.outputs if o.product_type.value == "green_coffee")
        share_ratio = float(i.quantity_kg) / float(i.batch.total_cherry_kg)
        output_share_kg += batch_output * share_ratio
    return payable, pob_kg, output_share_kg, last_date


@router.get("/farmer-settlement")
def farmer_settlement(request: Request, db: Session = Depends(get_db), user=Depends(require_role(*CAN_VIEW_FINANCIALS))):
    farmers = db.query(models.Farmer).order_by(models.Farmer.full_name).all()
    rows = []
    for f in farmers:
        payable, pob_kg, output_share_kg, last_date = _compute_farmer_settlement(db, f)
        if payable or pob_kg:
            rows.append(
                {"farmer": f, "payable": payable, "pob_kg": pob_kg, "output_share_kg": output_share_kg, "last_settled": last_date}
            )
    history = (
        db.query(models.FarmerSettlement)
        .filter(models.FarmerSettlement.status == models.SettlementStatus.paid)
        .order_by(models.FarmerSettlement.created_at.desc())
        .limit(50)
        .all()
    )
    return templates.TemplateResponse(
        "reports/farmer_settlement.html", {"request": request, "user": user, "rows": rows, "history": history}
    )


@router.post("/farmer-settlement/{farmer_id}/settle")
def settle_farmer(farmer_id: int, db: Session = Depends(get_db), user=Depends(require_role(*CAN_VIEW_FINANCIALS))):
    farmer = db.query(models.Farmer).get(farmer_id)
    payable, pob_kg, output_share_kg, _ = _compute_farmer_settlement(db, farmer)
    if not payable and not pob_kg:
        return RedirectResponse("/reports/farmer-settlement?error=Nothing to settle for this farmer", status_code=303)
    settlement = models.FarmerSettlement(
        farmer_id=farmer_id,
        as_of_date=date.today(),
        purchase_payable=payable,
        pob_output_share_kg=output_share_kg,
        status=models.SettlementStatus.paid,
        paid_date=date.today(),
        paid_by=user.id,
    )
    db.add(settlement)
    db.commit()
    log_action(
        db, user, models.AuditAction.create, "farmer_settlement", settlement.id,
        f"Settled {farmer.full_name}: payable {payable:.2f}, output share {output_share_kg:.2f}kg",
    )
    return RedirectResponse("/reports/farmer-settlement?success=Settlement recorded", status_code=303)
