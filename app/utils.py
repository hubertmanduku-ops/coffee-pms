from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session


def next_sequence_number(db: Session, model, column, prefix: str) -> str:
    """Generate e.g. INT-20260809-0001 style numbers scoped to today's date."""
    today_str = date.today().strftime("%Y%m%d")
    like_pattern = f"{prefix}-{today_str}-%"
    count = db.query(func.count()).select_from(model).filter(column.like(like_pattern)).scalar()
    seq = (count or 0) + 1
    return f"{prefix}-{today_str}-{seq:04d}"
