from decimal import Decimal
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.audit import log_action
from app.database import get_db
from app.dependencies import CAN_DELETE, CAN_EDIT, require_login, require_role

router = APIRouter(prefix="/expenses", tags=["expenses"])
templates = Jinja2Templates(directory="app/templates")

CATEGORIES = ["Labor", "Fuel", "Transport", "Maintenance", "Utilities", "Packaging", "Other"]


@router.get("")
def list_expenses(request: Request, category: str = "", db: Session = Depends(get_db), user=Depends(require_login)):
    query = db.query(models.Expense)
    if category:
        query = query.filter(models.Expense.category == category)
    expenses = query.order_by(models.Expense.expense_date.desc()).all()
    total = sum(float(e.amount) for e in expenses)
    return templates.TemplateResponse(
        "expenses/list.html",
        {"request": request, "user": user, "expenses": expenses, "categories": CATEGORIES, "category": category, "total": total},
    )


@router.get("/new")
def new_expense_form(request: Request, db: Session = Depends(get_db), user=Depends(require_role(*CAN_EDIT))):
    batches = db.query(models.Batch).order_by(models.Batch.batch_date.desc()).limit(100).all()
    warehouses = db.query(models.Warehouse).filter(models.Warehouse.is_active.is_(True)).all()
    return templates.TemplateResponse(
        "expenses/form.html", {"request": request, "user": user, "categories": CATEGORIES, "batches": batches, "warehouses": warehouses}
    )


@router.post("/new")
def create_expense(
    expense_date: date = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    amount: Decimal = Form(...),
    batch_id: str = Form(""),
    warehouse_id: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require_role(*CAN_EDIT)),
):
    expense = models.Expense(
        expense_date=expense_date,
        category=category,
        description=description,
        amount=amount,
        batch_id=int(batch_id) if batch_id else None,
        warehouse_id=int(warehouse_id) if warehouse_id else None,
        recorded_by=user.id,
    )
    db.add(expense)
    db.commit()
    log_action(db, user, models.AuditAction.create, "expense", expense.id, f"Recorded {category} expense of {amount}")
    return RedirectResponse("/expenses?success=Expense recorded", status_code=303)


@router.post("/{expense_id}/delete")
def delete_expense(expense_id: int, db: Session = Depends(get_db), user=Depends(require_role(*CAN_DELETE))):
    expense = db.query(models.Expense).get(expense_id)
    db.delete(expense)
    db.commit()
    log_action(db, user, models.AuditAction.delete, "expense", expense_id, "Deleted expense")
    return RedirectResponse("/expenses?success=Expense deleted", status_code=303)
