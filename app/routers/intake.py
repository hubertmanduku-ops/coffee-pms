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

router = APIRouter(prefix="/intake", tags=["intake"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def list_intake(
    request: Request,
    farmer_id: int = None,
    unassigned: str = "",
    db: Session = Depends(get_db),
    user=Depends(require_login),
):
    query = db.query(models.CoffeeIntake)
    if farmer_id:
        query = query.filter(models.CoffeeIntake.farmer_id == farmer_id)
    if unassigned == "1":
        query = query.filter(models.CoffeeIntake.batch_id.is_(None))
    intakes = query.order_by(models.CoffeeIntake.intake_date.desc()).limit(300).all()
    farmers = db.query(models.Farmer).filter(models.Farmer.is_active.is_(True)).order_by(models.Farmer.full_name).all()
    return templates.TemplateResponse(
        "intake/list.html",
        {"request": request, "user": user, "intakes": intakes, "farmers": farmers, "farmer_id": farmer_id, "unassigned": unassigned},
    )


@router.get("/new")
def new_intake_form(request: Request, db: Session = Depends(get_db), user=Depends(require_role(*CAN_EDIT))):
    farmers = db.query(models.Farmer).filter(models.Farmer.is_active.is_(True)).order_by(models.Farmer.full_name).all()
    return templates.TemplateResponse("intake/form.html", {"request": request, "user": user, "farmers": farmers, "intake": None})


@router.post("/new")
def create_intake(
    farmer_id: int = Form(...),
    intake_date: date = Form(...),
    quantity_kg: Decimal = Form(...),
    arrangement_type: str = Form(...),
    price_per_kg: str = Form(""),
    quality_grade: str = Form(""),
    moisture_content: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require_role(*CAN_EDIT)),
):
    total_amount = None
    price = None
    if arrangement_type == "purchase" and price_per_kg:
        price = Decimal(price_per_kg)
        total_amount = price * quantity_kg
    number = next_sequence_number(db, models.CoffeeIntake, models.CoffeeIntake.intake_number, "INT")
    intake = models.CoffeeIntake(
        intake_number=number,
        farmer_id=farmer_id,
        intake_date=intake_date,
        quantity_kg=quantity_kg,
        arrangement_type=arrangement_type,
        price_per_kg=price,
        total_amount=total_amount,
        quality_grade=quality_grade or None,
        moisture_content=Decimal(moisture_content) if moisture_content else None,
        recorded_by=user.id,
    )
    db.add(intake)
    db.commit()
    log_action(db, user, models.AuditAction.create, "coffee_intake", intake.id, f"Recorded intake {intake.intake_number} ({quantity_kg} kg)")
    return RedirectResponse(f"/intake?success=Intake {number} recorded", status_code=303)


@router.get("/{intake_id}")
def intake_detail(intake_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_login)):
    intake = db.query(models.CoffeeIntake).get(intake_id)
    return templates.TemplateResponse("intake/detail.html", {"request": request, "user": user, "intake": intake})


@router.post("/{intake_id}/delete")
def delete_intake(intake_id: int, db: Session = Depends(get_db), user=Depends(require_role(*CAN_DELETE))):
    intake = db.query(models.CoffeeIntake).get(intake_id)
    if intake.batch_id:
        return RedirectResponse("/intake?error=Cannot delete an intake already assigned to a batch", status_code=303)
    number = intake.intake_number
    db.delete(intake)
    db.commit()
    log_action(db, user, models.AuditAction.delete, "coffee_intake", intake_id, f"Deleted intake {number}")
    return RedirectResponse("/intake?success=Intake deleted", status_code=303)
