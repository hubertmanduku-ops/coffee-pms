from decimal import Decimal
from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.audit import log_action
from app.database import get_db
from app.dependencies import CAN_EDIT, require_login, require_role

router = APIRouter(prefix="/processing", tags=["processing"])
templates = Jinja2Templates(directory="app/templates")


def _post_inventory_in(db: Session, warehouse_id: int, product_type: str, quantity_kg: Decimal, reference_type: str, reference_id: int, user, notes: str = ""):
    txn = models.InventoryTransaction(
        warehouse_id=warehouse_id,
        product_type=product_type,
        transaction_type=models.TransactionType.in_,
        quantity_kg=quantity_kg,
        reference_type=reference_type,
        reference_id=reference_id,
        recorded_by=user.id,
        notes=notes,
    )
    db.add(txn)
    stock = (
        db.query(models.WarehouseStock)
        .filter(models.WarehouseStock.warehouse_id == warehouse_id, models.WarehouseStock.product_type == product_type)
        .first()
    )
    if not stock:
        stock = models.WarehouseStock(warehouse_id=warehouse_id, product_type=product_type, quantity_kg=0)
        db.add(stock)
        db.flush()
    stock.quantity_kg = (stock.quantity_kg or Decimal(0)) + quantity_kg


@router.get("")
def list_processing(request: Request, db: Session = Depends(get_db), user=Depends(require_login)):
    stages = db.query(models.ProcessingStage).order_by(models.ProcessingStage.start_datetime.desc()).limit(100).all()
    outputs = db.query(models.ProcessingOutput).order_by(models.ProcessingOutput.output_date.desc()).limit(100).all()
    return templates.TemplateResponse("processing/list.html", {"request": request, "user": user, "stages": stages, "outputs": outputs})


@router.get("/stage/new")
def new_stage_form(batch_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_role(*CAN_EDIT))):
    batch = db.query(models.Batch).get(batch_id)
    return templates.TemplateResponse(
        "processing/stage_form.html",
        {"request": request, "user": user, "batch": batch, "stage_types": [s.value for s in models.StageType]},
    )


@router.post("/stage/new")
def create_stage(
    batch_id: int = Form(...),
    stage: str = Form(...),
    start_datetime: datetime = Form(...),
    end_datetime: datetime | None = Form(None),
    parameters: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require_role(*CAN_EDIT)),
):
    record = models.ProcessingStage(
        batch_id=batch_id,
        stage=stage,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        parameters=parameters,
        notes=notes,
        recorded_by=user.id,
    )
    db.add(record)
    db.commit()
    log_action(db, user, models.AuditAction.create, "processing_stage", record.id, f"Logged {stage} stage for batch {batch_id}")
    return RedirectResponse(f"/batches/{batch_id}?success=Stage recorded", status_code=303)


@router.get("/output/new")
def new_output_form(batch_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_role(*CAN_EDIT))):
    batch = db.query(models.Batch).get(batch_id)
    warehouses = db.query(models.Warehouse).filter(models.Warehouse.is_active.is_(True)).all()
    return templates.TemplateResponse(
        "processing/output_form.html",
        {"request": request, "user": user, "batch": batch, "warehouses": warehouses, "product_types": [p.value for p in models.ProductType]},
    )


@router.post("/output/new")
def create_output(
    batch_id: int = Form(...),
    output_date: date = Form(...),
    product_type: str = Form(...),
    quantity_kg: Decimal = Form(...),
    moisture_content: str = Form(""),
    warehouse_id: int = Form(...),
    destination: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require_role(*CAN_EDIT)),
):
    output = models.ProcessingOutput(
        batch_id=batch_id,
        output_date=output_date,
        product_type=product_type,
        quantity_kg=quantity_kg,
        moisture_content=Decimal(moisture_content) if moisture_content else None,
        warehouse_id=warehouse_id,
        destination=destination if product_type == "parchment" and destination else None,
        recorded_by=user.id,
    )
    db.add(output)
    db.flush()
    _post_inventory_in(db, warehouse_id, product_type, quantity_kg, "processing_output", output.id, user, notes=f"Output from batch {batch_id}")
    db.commit()
    log_action(db, user, models.AuditAction.create, "processing_output", output.id, f"Recorded {quantity_kg}kg {product_type} for batch {batch_id}")

    if product_type == "parchment" and quantity_kg:
        batch = db.query(models.Batch).get(batch_id)
        rates = db.query(models.CostRateSettings).get(1)
        if batch and batch.total_cherry_kg and rates:
            loss_ratio = float(batch.total_cherry_kg) / float(quantity_kg)
            if loss_ratio < float(rates.loss_ratio_min) or loss_ratio > float(rates.loss_ratio_max):
                return RedirectResponse(
                    f"/batches/{batch_id}?warning=Cherry:parchment loss ratio {loss_ratio:.2f} is outside the expected "
                    f"{rates.loss_ratio_min}–{rates.loss_ratio_max} range — verify the weights",
                    status_code=303,
                )
    return RedirectResponse(f"/batches/{batch_id}?success=Output recorded and added to inventory", status_code=303)
