from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.dependencies import ADMIN_ONLY, require_role

router = APIRouter(prefix="/audit-log", tags=["audit"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def view_audit_log(request: Request, db: Session = Depends(get_db), user=Depends(require_role(*ADMIN_ONLY))):
    entries = db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(300).all()
    return templates.TemplateResponse("audit/list.html", {"request": request, "user": user, "entries": entries})
