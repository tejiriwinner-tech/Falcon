"""Create capital_cycles table for V10 Phase 2 Capital Cycle Foundation & Accounting

Revision ID: 0006_v10_capital_cycle
Revises: 0005_v10_performance_journal
Create Date: 2026-09-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_v10_capital_cycle"
down_revision = "0005_v10_performance_journal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "capital_cycles",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("cycle_id", sa.String(length=64), nullable=False),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("starting_capital", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("target_capital", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("active_trading_capital", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("protected_profit", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0.00"),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_capital", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("realized_profit", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("next_cycle_allocation", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", name="uq_capital_cycles_cycle_id"),
        sa.UniqueConstraint("cycle_number", name="uq_capital_cycles_cycle_number"),
    )

    op.create_index("ix_capital_cycles_status", "capital_cycles", ["status"])
    op.create_index("ix_capital_cycles_cycle_number", "capital_cycles", ["cycle_number"])
    op.create_index(
        "uq_capital_cycles_active",
        "capital_cycles",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("uq_capital_cycles_active", table_name="capital_cycles")
    op.drop_index("ix_capital_cycles_cycle_number", table_name="capital_cycles")
    op.drop_index("ix_capital_cycles_status", table_name="capital_cycles")
    op.drop_table("capital_cycles")
