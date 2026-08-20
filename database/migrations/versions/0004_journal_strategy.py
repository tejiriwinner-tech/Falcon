"""Add strategy_id to trade journal entries

Revision ID: 0004_journal_strategy
Revises: 0003_market_data
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_journal_strategy"
down_revision = "0003_market_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trade_journal",
        sa.Column("strategy_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_trade_journal_strategy_id", "trade_journal", ["strategy_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_trade_journal_strategy_id", table_name="trade_journal")
    op.drop_column("trade_journal", "strategy_id")
