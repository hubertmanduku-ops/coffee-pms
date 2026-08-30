from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.audit import log_action
from app.database import get_db
from app.dependencies import require_login
from app.security import hash_password, verify_password

router = APIRouter(prefix="/account", tags=["account"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/change-password")
def change_password_form(request: Request, user=Depends(require_login)):
    return templates.TemplateResponse("account/change_password.html", {"request": request, "user": user, "error": None})


@router.post("/change-password")
def change_password_submit(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(require_login),
):
    if not verify_password(current_password, user.password_hash):
        return templates.TemplateResponse(
            "account/change_password.html",
            {"request": request, "user": user, "error": "Current password is incorrect"},
            status_code=400,
        )
    if len(new_password) < 8:
        return templates.TemplateResponse(
            "account/change_password.html",
            {"request": request, "user": user, "error": "New password must be at least 8 characters"},
            status_code=400,
        )
    if new_password != confirm_password:
        return templates.TemplateResponse(
            "account/change_password.html",
            {"request": request, "user": user, "error": "New password and confirmation do not match"},
            status_code=400,
        )
    user.password_hash = hash_password(new_password)
    db.commit()
    log_action(db, user, models.AuditAction.update, "user", user.id, f"{user.username} changed their password")
    return RedirectResponse("/account/change-password?success=Password updated", status_code=303)
