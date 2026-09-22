"""Add initial_monetary_risk column to trade_journal for V10 Phase 5A.1

Revision ID: 0007_v10_initial_monetary_risk
Revises: 0006_v10_capital_cycle
Create Date: 2026-09-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_v10_initial_monetary_risk"
down_revision = "0006_v10_capital_cycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trade_journal",
        sa.Column(
            "initial_monetary_risk",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("trade_journal", "initial_monetary_risk")
