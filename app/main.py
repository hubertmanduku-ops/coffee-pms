from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import Base, SessionLocal, engine
from app import models
from app.security import hash_password

from app.routers import auth, dashboard, farmers, intake, batches, processing, inventory, expenses, sales, reports, users, audit_log

app = FastAPI(title=settings.APP_NAME)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(farmers.router)
app.include_router(intake.router)
app.include_router(batches.router)
app.include_router(processing.router)
app.include_router(inventory.router)
app.include_router(expenses.router)
app.include_router(sales.router)
app.include_router(reports.router)
app.include_router(users.router)
app.include_router(audit_log.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # Used by require_login to bounce unauthenticated users to /login.
    if exc.status_code == 303 and exc.headers and "Location" in exc.headers:
        return RedirectResponse(url=exc.headers["Location"], status_code=303)
    if exc.status_code == 403:
        return HTMLResponse(
            content=(
                "<div style='font-family:sans-serif;padding:3rem;text-align:center;'>"
                "<h3>403 — Not authorized</h3><p>You don't have permission to perform this action."
                "</p><a href='/'>Back to dashboard</a></div>"
            ),
            status_code=403,
        )
    if exc.status_code == 404:
        return HTMLResponse(
            content=(
                "<div style='font-family:sans-serif;padding:3rem;text-align:center;'>"
                "<h3>404 — Not found</h3><a href='/'>Back to dashboard</a></div>"
            ),
            status_code=404,
        )
    return HTMLResponse(content=f"<p>Error {exc.status_code}: {exc.detail}</p>", status_code=exc.status_code)


@app.on_event("startup")
def startup_seed():
    """Create tables if absent and seed a default admin user + the two fixed warehouses.

    Sufficient for this project's scope (see Development Plan). For larger schema evolution,
    Alembic migrations can be introduced later without changing this bootstrap logic.
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(models.User).first():
            admin = models.User(
                username="admin",
                full_name="System Administrator",
                password_hash=hash_password("admin123"),
                role=models.UserRole.admin,
            )
            db.add(admin)
        if not db.query(models.Warehouse).first():
            db.add(models.Warehouse(name="Warehouse A", location="Main store"))
            db.add(models.Warehouse(name="Warehouse B", location="Secondary store"))
        db.commit()
    finally:
        db.close()
