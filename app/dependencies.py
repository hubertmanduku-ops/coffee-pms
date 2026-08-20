from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.database import get_db
from app.security import read_session_token


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User | None:
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        return None
    user_id = read_session_token(token)
    if not user_id:
        return None
    user = db.query(models.User).filter(models.User.id == user_id, models.User.is_active.is_(True)).first()
    return user


def require_login(user: models.User | None = Depends(get_current_user)) -> models.User:
    if not user:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return user


def require_role(*roles: str):
    """Usage: Depends(require_role('admin', 'manager'))"""

    def checker(user: models.User = Depends(require_login)) -> models.User:
        if user.role.value not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this action")
        return user

    return checker


# Convenience role groups used across routers
CAN_EDIT = ("admin", "manager", "clerk")  # create/update operational records
CAN_DELETE = ("admin", "manager")  # delete operational records
CAN_VIEW_FINANCIALS = ("admin", "manager")  # financial reports, settlement worksheet
ADMIN_ONLY = ("admin",)
