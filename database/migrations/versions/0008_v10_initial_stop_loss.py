"""Add initial_stop_loss column to trade_journal for V10 Phase 5A.1

Revision ID: 0008_v10_initial_stop_loss
Revises: 0007_v10_initial_monetary_risk
Create Date: 2026-10-22
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_v10_initial_stop_loss"
down_revision = "0007_v10_initial_monetary_risk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trade_journal",
        sa.Column(
            "initial_stop_loss",
            sa.Float(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("trade_journal", "initial_stop_loss")
