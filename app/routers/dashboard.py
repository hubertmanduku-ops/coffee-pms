from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.dependencies import require_login

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db), user=Depends(require_login)):
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_start = today.replace(day=1)

    # --- Core volume metrics -------------------------------------------------
    today_intake_kg = (
        db.query(func.coalesce(func.sum(models.CoffeeIntake.quantity_kg), 0))
        .filter(models.CoffeeIntake.intake_date == today)
        .scalar()
    )
    week_intake_kg = (
        db.query(func.coalesce(func.sum(models.CoffeeIntake.quantity_kg), 0))
        .filter(models.CoffeeIntake.intake_date >= week_ago)
        .scalar()
    )
    month_intake_kg = (
        db.query(func.coalesce(func.sum(models.CoffeeIntake.quantity_kg), 0))
        .filter(models.CoffeeIntake.intake_date >= month_start)
        .scalar()
    )
    total_intake_kg = db.query(func.coalesce(func.sum(models.CoffeeIntake.quantity_kg), 0)).scalar()

    # --- Farmers ---------------------------------------------------------------
    total_farmers = db.query(func.count(models.Farmer.id)).filter(models.Farmer.is_active.is_(True)).scalar()

    top_farmers = (
        db.query(models.Farmer.full_name, func.coalesce(func.sum(models.CoffeeIntake.quantity_kg), 0).label("kg"))
        .join(models.CoffeeIntake, models.CoffeeIntake.farmer_id == models.Farmer.id)
        .group_by(models.Farmer.full_name)
        .order_by(func.sum(models.CoffeeIntake.quantity_kg).desc())
        .limit(5)
        .all()
    )

    # --- Batches -----------------------------------------------------------------
    open_batches = db.query(func.count(models.Batch.id)).filter(models.Batch.status == models.BatchStatus.open).scalar()
    processing_batches = (
        db.query(func.count(models.Batch.id)).filter(models.Batch.status == models.BatchStatus.processing).scalar()
    )
    completed_batches = (
        db.query(func.count(models.Batch.id)).filter(models.Batch.status == models.BatchStatus.completed).scalar()
    )

    batches_with_cherry = db.query(models.Batch).filter(models.Batch.total_cherry_kg > 0).all()
    recovery_values = []
    for b in batches_with_cherry:
        out_kg = sum(float(o.quantity_kg) for o in b.outputs if o.product_type.value == "green_coffee")
        if out_kg > 0:
            recovery_values.append(out_kg / float(b.total_cherry_kg) * 100)
    avg_recovery_pct = sum(recovery_values) / len(recovery_values) if recovery_values else 0

    # --- Inventory -----------------------------------------------------------------
    stock = db.query(models.WarehouseStock).all()
    green_coffee_stock_kg = sum(float(s.quantity_kg) for s in stock if s.product_type.value == "green_coffee")
    parchment_stock_kg = sum(float(s.quantity_kg) for s in stock if s.product_type.value == "parchment")
    cherry_stock_kg = sum(float(s.quantity_kg) for s in stock if s.product_type.value == "cherry")

    # --- Money ------------------------------------------------------------------------
    month_expenses = (
        db.query(func.coalesce(func.sum(models.Expense.amount), 0))
        .filter(models.Expense.expense_date >= month_start)
        .scalar()
    )
    month_sales = (
        db.query(func.coalesce(func.sum(models.Sale.total_amount), 0))
        .filter(models.Sale.sale_date >= month_start)
        .scalar()
    )
    net_this_month = float(month_sales) - float(month_expenses)

    month_purchase_cost = (
        db.query(func.coalesce(func.sum(models.CoffeeIntake.total_amount), 0))
        .filter(
            models.CoffeeIntake.intake_date >= month_start,
            models.CoffeeIntake.arrangement_type == models.ArrangementType.purchase,
        )
        .scalar()
    )

    # --- 7-day intake trend, for the chart -------------------------------------------
    trend_rows = (
        db.query(models.CoffeeIntake.intake_date, func.coalesce(func.sum(models.CoffeeIntake.quantity_kg), 0))
        .filter(models.CoffeeIntake.intake_date >= week_ago)
        .group_by(models.CoffeeIntake.intake_date)
        .all()
    )
    trend_by_date = {r[0]: float(r[1]) for r in trend_rows}
    intake_trend_labels = []
    intake_trend_values = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        intake_trend_labels.append(d.strftime("%a %d"))
        intake_trend_values.append(trend_by_date.get(d, 0))

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "today_intake_kg": today_intake_kg,
            "week_intake_kg": week_intake_kg,
            "month_intake_kg": month_intake_kg,
            "total_intake_kg": total_intake_kg,
            "total_farmers": total_farmers,
            "top_farmers": top_farmers,
            "open_batches": open_batches,
            "processing_batches": processing_batches,
            "completed_batches": completed_batches,
            "avg_recovery_pct": avg_recovery_pct,
            "stock": stock,
            "green_coffee_stock_kg": green_coffee_stock_kg,
            "parchment_stock_kg": parchment_stock_kg,
            "cherry_stock_kg": cherry_stock_kg,
            "month_expenses": month_expenses,
            "month_sales": month_sales,
            "net_this_month": net_this_month,
            "month_purchase_cost": month_purchase_cost,
            "intake_trend_labels": intake_trend_labels,
            "intake_trend_values": intake_trend_values,
        },
    )
