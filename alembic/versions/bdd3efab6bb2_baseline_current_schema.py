"""baseline current schema

A no-op marker revision. Every database up to this point (all core CPMS tables: users,
warehouses, farmers, coffee_intakes, batches, batch_intakes, processing_stages,
processing_outputs, warehouse_stock, inventory_transactions, expenses, sales, audit_logs)
was created via `Base.metadata.create_all()` at app startup, before Alembic was introduced.

- Existing/production databases (e.g. Railway): run `alembic stamp head` once, at this
  revision, to mark them as already here without re-running anything.
- Fresh databases: `Base.metadata.create_all()` still runs at app startup and creates the
  full current schema directly; this revision then simply has nothing to do.

Revision ID: bdd3efab6bb2
Revises:
Create Date: 2026-08-30 13:25:43.617621

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bdd3efab6bb2'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
