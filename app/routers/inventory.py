from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.audit import log_action
from app.database import get_db
from app.dependencies import CAN_EDIT, require_login, require_role

router = APIRouter(prefix="/inventory", tags=["inventory"])
templates = Jinja2Templates(directory="app/templates")


def _adjust_stock(db: Session, warehouse_id: int, product_type: str, delta: Decimal):
    stock = (
        db.query(models.WarehouseStock)
        .filter(models.WarehouseStock.warehouse_id == warehouse_id, models.WarehouseStock.product_type == product_type)
        .first()
    )
    if not stock:
        stock = models.WarehouseStock(warehouse_id=warehouse_id, product_type=product_type, quantity_kg=0)
        db.add(stock)
        db.flush()
    stock.quantity_kg = (stock.quantity_kg or Decimal(0)) + delta
    return stock


@router.get("")
def inventory_home(request: Request, db: Session = Depends(get_db), user=Depends(require_login)):
    warehouses = db.query(models.Warehouse).filter(models.Warehouse.is_active.is_(True)).all()
    stock = db.query(models.WarehouseStock).all()
    transactions = db.query(models.InventoryTransaction).order_by(models.InventoryTransaction.created_at.desc()).limit(100).all()
    return templates.TemplateResponse(
        "inventory/home.html",
        {"request": request, "user": user, "warehouses": warehouses, "stock": stock, "transactions": transactions},
    )


@router.get("/transfer")
def transfer_form(request: Request, db: Session = Depends(get_db), user=Depends(require_role(*CAN_EDIT))):
    warehouses = db.query(models.Warehouse).filter(models.Warehouse.is_active.is_(True)).all()
    return templates.TemplateResponse(
        "inventory/transfer_form.html",
        {"request": request, "user": user, "warehouses": warehouses, "product_types": [p.value for p in models.ProductType]},
    )


@router.post("/transfer")
def do_transfer(
    from_warehouse_id: int = Form(...),
    to_warehouse_id: int = Form(...),
    product_type: str = Form(...),
    quantity_kg: Decimal = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require_role(*CAN_EDIT)),
):
    if from_warehouse_id == to_warehouse_id:
        return RedirectResponse("/inventory?error=Source and destination warehouse must differ", status_code=303)
    source_stock = (
        db.query(models.WarehouseStock)
        .filter(models.WarehouseStock.warehouse_id == from_warehouse_id, models.WarehouseStock.product_type == product_type)
        .first()
    )
    available = source_stock.quantity_kg if source_stock else Decimal(0)
    if quantity_kg > available:
        return RedirectResponse(f"/inventory?error=Insufficient stock ({available} kg available)", status_code=303)

    out_txn = models.InventoryTransaction(
        warehouse_id=from_warehouse_id, product_type=product_type, transaction_type=models.TransactionType.transfer_out,
        quantity_kg=quantity_kg, reference_type="transfer", reference_id=to_warehouse_id, recorded_by=user.id, notes=notes,
    )
    in_txn = models.InventoryTransaction(
        warehouse_id=to_warehouse_id, product_type=product_type, transaction_type=models.TransactionType.transfer_in,
        quantity_kg=quantity_kg, reference_type="transfer", reference_id=from_warehouse_id, recorded_by=user.id, notes=notes,
    )
    db.add_all([out_txn, in_txn])
    _adjust_stock(db, from_warehouse_id, product_type, -quantity_kg)
    _adjust_stock(db, to_warehouse_id, product_type, quantity_kg)
    db.commit()
    log_action(db, user, models.AuditAction.create, "inventory_transfer", None, f"Transferred {quantity_kg}kg {product_type} between warehouses")
    return RedirectResponse("/inventory?success=Transfer recorded", status_code=303)


@router.get("/adjust")
def adjust_form(request: Request, db: Session = Depends(get_db), user=Depends(require_role(*CAN_EDIT))):
    warehouses = db.query(models.Warehouse).filter(models.Warehouse.is_active.is_(True)).all()
    return templates.TemplateResponse(
        "inventory/adjust_form.html",
        {"request": request, "user": user, "warehouses": warehouses, "product_types": [p.value for p in models.ProductType]},
    )


@router.post("/adjust")
def do_adjustment(
    warehouse_id: int = Form(...),
    product_type: str = Form(...),
    quantity_kg: Decimal = Form(...),
    notes: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(require_role(*CAN_EDIT)),
):
    txn = models.InventoryTransaction(
        warehouse_id=warehouse_id, product_type=product_type, transaction_type=models.TransactionType.adjustment,
        quantity_kg=quantity_kg, reference_type="manual_adjustment", recorded_by=user.id, notes=notes,
    )
    db.add(txn)
    _adjust_stock(db, warehouse_id, product_type, quantity_kg)
    db.commit()
    log_action(db, user, models.AuditAction.create, "inventory_adjustment", txn.id, f"Adjusted {quantity_kg}kg {product_type}: {notes}")
    return RedirectResponse("/inventory?success=Adjustment recorded", status_code=303)
