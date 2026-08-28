from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.audit import log_action
from app.database import get_db
from app.dependencies import ADMIN_ONLY, require_role
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def list_users(request: Request, db: Session = Depends(get_db), user=Depends(require_role(*ADMIN_ONLY))):
    users = db.query(models.User).order_by(models.User.username).all()
    return templates.TemplateResponse("users/list.html", {"request": request, "user": user, "users": users})


@router.get("/new")
def new_user_form(request: Request, user=Depends(require_role(*ADMIN_ONLY))):
    return templates.TemplateResponse("users/form.html", {"request": request, "user": user})


@router.post("/new")
def create_user(
    username: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(require_role(*ADMIN_ONLY)),
):
    if db.query(models.User).filter(models.User.username == username).first():
        return RedirectResponse("/users/new?error=Username already exists", status_code=303)
    new_user = models.User(username=username, full_name=full_name, password_hash=hash_password(password), role=role)
    db.add(new_user)
    db.commit()
    log_action(db, user, models.AuditAction.create, "user", new_user.id, f"Created user {username} ({role})")
    return RedirectResponse("/users?success=User created", status_code=303)


@router.post("/{user_id}/toggle-active")
def toggle_active(user_id: int, db: Session = Depends(get_db), user=Depends(require_role(*ADMIN_ONLY))):
    target = db.query(models.User).get(user_id)
    target.is_active = not target.is_active
    db.commit()
    log_action(db, user, models.AuditAction.update, "user", user_id, f"{'Activated' if target.is_active else 'Deactivated'} user {target.username}")
    return RedirectResponse("/users?success=User updated", status_code=303)
