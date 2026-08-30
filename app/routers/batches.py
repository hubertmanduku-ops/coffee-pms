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
from app.utils import next_sequence_number

router = APIRouter(prefix="/batches", tags=["batches"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def list_batches(request: Request, status: str = "", db: Session = Depends(get_db), user=Depends(require_login)):
    query = db.query(models.Batch)
    if status:
        query = query.filter(models.Batch.status == status)
    batches = query.order_by(models.Batch.batch_date.desc()).all()
    return templates.TemplateResponse("batches/list.html", {"request": request, "user": user, "batches": batches, "status": status})


@router.get("/new")
def new_batch_form(request: Request, user=Depends(require_role(*CAN_EDIT))):
    return templates.TemplateResponse("batches/form.html", {"request": request, "user": user})


@router.post("/new")
def create_batch(
    batch_date: date = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require_role(*CAN_EDIT)),
):
    number = next_sequence_number(db, models.Batch, models.Batch.batch_number, "BAT")
    batch = models.Batch(batch_number=number, batch_date=batch_date, notes=notes, created_by=user.id)
    db.add(batch)
    db.commit()
    log_action(db, user, models.AuditAction.create, "batch", batch.id, f"Created batch {batch.batch_number}")
    return RedirectResponse(f"/batches/{batch.id}?success=Batch {number} created", status_code=303)


@router.get("/{batch_id}")
def batch_detail(batch_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_login)):
    batch = db.query(models.Batch).get(batch_id)
    unassigned_intakes = (
        db.query(models.CoffeeIntake)
        .filter(models.CoffeeIntake.batch_id.is_(None))
        .order_by(models.CoffeeIntake.intake_date.desc())
        .all()
    )
    warehouses = db.query(models.Warehouse).filter(models.Warehouse.is_active.is_(True)).all()
    total_output = sum(float(o.quantity_kg) for o in batch.outputs)
    recovery_pct = (total_output / float(batch.total_cherry_kg) * 100) if batch.total_cherry_kg else 0
    rates = db.query(models.CostRateSettings).get(1)
    return templates.TemplateResponse(
        "batches/detail.html",
        {
            "request": request,
            "user": user,
            "batch": batch,
            "unassigned_intakes": unassigned_intakes,
            "warehouses": warehouses,
            "total_output": total_output,
            "recovery_pct": recovery_pct,
            "rates": rates,
            "stage_types": [s.value for s in models.StageType],
            "product_types": [p.value for p in models.ProductType],
        },
    )


@router.post("/{batch_id}/add-intake")
def add_intake_to_batch(
    batch_id: int,
    intake_id: int = Form(...),
    db: Session = Depends(get_db),
    user=Depends(require_role(*CAN_EDIT)),
):
    batch = db.query(models.Batch).get(batch_id)
    intake = db.query(models.CoffeeIntake).get(intake_id)
    if intake.batch_id is not None:
        return RedirectResponse(f"/batches/{batch_id}?error=Intake already assigned to a batch", status_code=303)
    intake.batch_id = batch.id
    db.add(models.BatchIntake(batch_id=batch.id, intake_id=intake.id, quantity_kg=intake.quantity_kg))
    batch.total_cherry_kg = (batch.total_cherry_kg or Decimal(0)) + intake.quantity_kg
    if batch.status == models.BatchStatus.open:
        batch.status = models.BatchStatus.processing
    db.commit()
    log_action(db, user, models.AuditAction.update, "batch", batch.id, f"Added intake {intake.intake_number} to batch")
    return RedirectResponse(f"/batches/{batch_id}?success=Intake added to batch", status_code=303)


@router.post("/{batch_id}/status")
def update_batch_status(
    batch_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(require_role(*CAN_EDIT)),
):
    batch = db.query(models.Batch).get(batch_id)
    batch.status = status
    db.commit()
    log_action(db, user, models.AuditAction.update, "batch", batch.id, f"Batch status set to {status}")
    return RedirectResponse(f"/batches/{batch_id}?success=Batch status updated", status_code=303)


@router.post("/{batch_id}/delete")
def delete_batch(batch_id: int, db: Session = Depends(get_db), user=Depends(require_role(*CAN_DELETE))):
    batch = db.query(models.Batch).get(batch_id)
    if batch.composition:
        return RedirectResponse("/batches?error=Cannot delete a batch that has intakes assigned", status_code=303)
    number = batch.batch_number
    db.delete(batch)
    db.commit()
    log_action(db, user, models.AuditAction.delete, "batch", batch_id, f"Deleted batch {number}")
    return RedirectResponse("/batches?success=Batch deleted", status_code=303)
