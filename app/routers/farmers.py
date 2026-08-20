from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.audit import log_action
from app.database import get_db
from app.dependencies import CAN_DELETE, CAN_EDIT, require_login, require_role
from app.utils import next_sequence_number

router = APIRouter(prefix="/farmers", tags=["farmers"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def list_farmers(request: Request, q: str = "", db: Session = Depends(get_db), user=Depends(require_login)):
    query = db.query(models.Farmer)
    if q:
        query = query.filter(models.Farmer.full_name.ilike(f"%{q}%"))
    farmers = query.order_by(models.Farmer.full_name).all()
    return templates.TemplateResponse(
        "farmers/list.html", {"request": request, "user": user, "farmers": farmers, "q": q}
    )


@router.get("/new")
def new_farmer_form(request: Request, user=Depends(require_role(*CAN_EDIT))):
    return templates.TemplateResponse(
        "farmers/form.html", {"request": request, "user": user, "farmer": None}
    )


@router.post("/new")
def create_farmer(
    request: Request,
    full_name: str = Form(...),
    phone: str = Form(""),
    national_id: str = Form(""),
    location: str = Form(""),
    default_arrangement: str = Form("purchase"),
    bank_account: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require_role(*CAN_EDIT)),
):
    code = next_sequence_number(db, models.Farmer, models.Farmer.farmer_code, "FRM")
    farmer = models.Farmer(
        farmer_code=code,
        full_name=full_name,
        phone=phone,
        national_id=national_id,
        location=location,
        default_arrangement=default_arrangement,
        bank_account=bank_account,
    )
    db.add(farmer)
    db.commit()
    log_action(db, user, models.AuditAction.create, "farmer", farmer.id, f"Created farmer {farmer.full_name}")
    return RedirectResponse(f"/farmers?success=Farmer {farmer.full_name} created", status_code=303)


@router.get("/{farmer_id}")
def farmer_detail(farmer_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_login)):
    farmer = db.query(models.Farmer).get(farmer_id)
    intakes = (
        db.query(models.CoffeeIntake)
        .filter(models.CoffeeIntake.farmer_id == farmer_id)
        .order_by(models.CoffeeIntake.intake_date.desc())
        .all()
    )
    total_kg = sum(float(i.quantity_kg) for i in intakes)
    total_payable = sum(float(i.total_amount or 0) for i in intakes if i.arrangement_type.value == "purchase")
    return templates.TemplateResponse(
        "farmers/detail.html",
        {
            "request": request,
            "user": user,
            "farmer": farmer,
            "intakes": intakes,
            "total_kg": total_kg,
            "total_payable": total_payable,
        },
    )


@router.get("/{farmer_id}/edit")
def edit_farmer_form(farmer_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_role(*CAN_EDIT))):
    farmer = db.query(models.Farmer).get(farmer_id)
    return templates.TemplateResponse("farmers/form.html", {"request": request, "user": user, "farmer": farmer})


@router.post("/{farmer_id}/edit")
def update_farmer(
    farmer_id: int,
    full_name: str = Form(...),
    phone: str = Form(""),
    national_id: str = Form(""),
    location: str = Form(""),
    default_arrangement: str = Form("purchase"),
    bank_account: str = Form(""),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
    user=Depends(require_role(*CAN_EDIT)),
):
    farmer = db.query(models.Farmer).get(farmer_id)
    farmer.full_name = full_name
    farmer.phone = phone
    farmer.national_id = national_id
    farmer.location = location
    farmer.default_arrangement = default_arrangement
    farmer.bank_account = bank_account
    farmer.is_active = is_active
    db.commit()
    log_action(db, user, models.AuditAction.update, "farmer", farmer.id, f"Updated farmer {farmer.full_name}")
    return RedirectResponse(f"/farmers/{farmer_id}?success=Farmer updated", status_code=303)


@router.post("/{farmer_id}/delete")
def delete_farmer(farmer_id: int, db: Session = Depends(get_db), user=Depends(require_role(*CAN_DELETE))):
    farmer = db.query(models.Farmer).get(farmer_id)
    name = farmer.full_name
    db.delete(farmer)
    db.commit()
    log_action(db, user, models.AuditAction.delete, "farmer", farmer_id, f"Deleted farmer {name}")
    return RedirectResponse("/farmers?success=Farmer deleted", status_code=303)
