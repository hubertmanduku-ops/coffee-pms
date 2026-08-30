"""add costing settings, farmer settlements, parchment destination

Revision ID: d954fd8ecc24
Revises: bdd3efab6bb2
Create Date: 2026-08-30 13:26:32.983908

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'd954fd8ecc24'
down_revision: Union[str, None] = 'bdd3efab6bb2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guarded with existence checks: app/main.py's Base.metadata.create_all() at startup may
    # have already created these tables/column (it runs on every boot and is additive), e.g. if
    # the app deployed and booted before this migration was run against the same database. Each
    # step is skipped if it already exists, so this migration is safe to run in either order.
    bind = op.get_bind()
    insp = inspect(bind)
    existing_tables = insp.get_table_names()

    if 'cost_rate_settings' not in existing_tables:
        op.create_table('cost_rate_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('parchment_outturn_pct', sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column('milling_recovery_pct', sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column('pulping_cost_per_kg_cherry', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('milling_cost_per_kg_cherry', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('marketing_cost_per_kg_green', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('bag_size_kg', sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column('bag_cost', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('transport_cost_per_kg_green', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('selling_price_usd_per_kg', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('fx_rate_kes_per_usd', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('loss_ratio_min', sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column('loss_ratio_max', sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
        )

    if 'farmer_settlements' not in existing_tables:
        op.create_table('farmer_settlements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('farmer_id', sa.Integer(), nullable=False),
        sa.Column('as_of_date', sa.Date(), nullable=False),
        sa.Column('purchase_payable', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('pob_output_share_kg', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('status', sa.Enum('pending', 'paid', name='settlementstatus'), nullable=False),
        sa.Column('paid_date', sa.Date(), nullable=False),
        sa.Column('paid_by', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['farmer_id'], ['farmers.id'], ),
        sa.ForeignKeyConstraint(['paid_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
        )

    existing_columns = [c['name'] for c in insp.get_columns('processing_outputs')]
    if 'destination' not in existing_columns:
        # `add_column` (unlike `create_table`) doesn't auto-create a referenced Postgres ENUM
        # type, so it's created explicitly here first.
        parchment_destination = postgresql.ENUM('mill', 'store', name='parchmentdestination')
        parchment_destination.create(bind, checkfirst=True)
        op.add_column('processing_outputs', sa.Column('destination', parchment_destination, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    existing_columns = [c['name'] for c in insp.get_columns('processing_outputs')]
    if 'destination' in existing_columns:
        op.drop_column('processing_outputs', 'destination')
        postgresql.ENUM(name='parchmentdestination').drop(bind, checkfirst=True)

    existing_tables = insp.get_table_names()
    if 'farmer_settlements' in existing_tables:
        op.drop_table('farmer_settlements')
        # `drop_table` (unlike `create_table`) doesn't auto-drop the Postgres ENUM type the
        # dropped table's column referenced, so it's dropped explicitly here.
        postgresql.ENUM(name='settlementstatus').drop(bind, checkfirst=True)

    if 'cost_rate_settings' in existing_tables:
        op.drop_table('cost_rate_settings')
