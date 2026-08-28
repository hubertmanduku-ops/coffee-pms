from decimal import Decimal
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.audit import log_action
from app.database import get_db
from app.dependencies import CAN_EDIT, require_login, require_role
from app.utils import next_sequence_number

router = APIRouter(prefix="/sales", tags=["sales"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def list_sales(request: Request, db: Session = Depends(get_db), user=Depends(require_login)):
    sales = db.query(models.Sale).order_by(models.Sale.sale_date.desc()).all()
    total_revenue = sum(float(s.total_amount) for s in sales)
    return templates.TemplateResponse("sales/list.html", {"request": request, "user": user, "sales": sales, "total_revenue": total_revenue})


@router.get("/new")
def new_sale_form(request: Request, db: Session = Depends(get_db), user=Depends(require_role(*CAN_EDIT))):
    warehouses = db.query(models.Warehouse).filter(models.Warehouse.is_active.is_(True)).all()
    stock = db.query(models.WarehouseStock).all()
    batches = db.query(models.Batch).order_by(models.Batch.batch_date.desc()).limit(100).all()
    return templates.TemplateResponse(
        "sales/form.html",
        {
            "request": request,
            "user": user,
            "warehouses": warehouses,
            "stock": stock,
            "batches": batches,
            "product_types": [p.value for p in models.ProductType],
        },
    )


@router.post("/new")
def create_sale(
    sale_date: date = Form(...),
    customer_name: str = Form(...),
    product_type: str = Form(...),
    quantity_kg: Decimal = Form(...),
    unit_price: Decimal = Form(...),
    warehouse_id: int = Form(...),
    batch_id: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require_role(*CAN_EDIT)),
):
    stock = (
        db.query(models.WarehouseStock)
        .filter(models.WarehouseStock.warehouse_id == warehouse_id, models.WarehouseStock.product_type == product_type)
        .first()
    )
    available = stock.quantity_kg if stock else Decimal(0)
    if quantity_kg > available:
        return RedirectResponse(f"/sales/new?error=Insufficient stock ({available} kg available)", status_code=303)

    number = next_sequence_number(db, models.Sale, models.Sale.sale_number, "SAL")
    total = quantity_kg * unit_price
    sale = models.Sale(
        sale_number=number,
        sale_date=sale_date,
        customer_name=customer_name,
        product_type=product_type,
        quantity_kg=quantity_kg,
        unit_price=unit_price,
        total_amount=total,
        warehouse_id=warehouse_id,
        batch_id=int(batch_id) if batch_id else None,
        recorded_by=user.id,
    )
    db.add(sale)
    db.flush()

    txn = models.InventoryTransaction(
        warehouse_id=warehouse_id,
        product_type=product_type,
        transaction_type=models.TransactionType.out,
        quantity_kg=quantity_kg,
        reference_type="sale",
        reference_id=sale.id,
        recorded_by=user.id,
        notes=f"Sale {number} to {customer_name}",
    )
    db.add(txn)
    stock.quantity_kg = stock.quantity_kg - quantity_kg
    db.commit()
    log_action(db, user, models.AuditAction.create, "sale", sale.id, f"Recorded sale {number} of {quantity_kg}kg {product_type} to {customer_name}")
    return RedirectResponse(f"/sales?success=Sale {number} recorded", status_code=303)
