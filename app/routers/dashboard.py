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
    open_batches = db.query(func.count(models.Batch.id)).filter(models.Batch.status != models.BatchStatus.completed).scalar()
    stock = db.query(models.WarehouseStock).all()
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
    recent_activity = db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(10).all()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "today_intake_kg": today_intake_kg,
            "week_intake_kg": week_intake_kg,
            "open_batches": open_batches,
            "stock": stock,
            "month_expenses": month_expenses,
            "month_sales": month_sales,
            "recent_activity": recent_activity,
        },
    )
