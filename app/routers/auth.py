from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.audit import log_action
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.security import create_session_token, verify_password

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login")
def login_form(request: Request, user: models.User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid username or password"}, status_code=400
        )
    token = create_session_token(user.id)
    log_action(db, user, models.AuditAction.login, "user", user.id, f"{user.username} logged in")
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        settings.SESSION_COOKIE_NAME,
        token,
        max_age=settings.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.ENV == "production",
    )
    return response


@router.get("/logout")
def logout(request: Request, db: Session = Depends(get_db), user: models.User | None = Depends(get_current_user)):
    if user:
        log_action(db, user, models.AuditAction.logout, "user", user.id, f"{user.username} logged out")
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(settings.SESSION_COOKIE_NAME)
    return response
