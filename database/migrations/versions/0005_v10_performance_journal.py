"""Add V10 performance journal execution, MFE/MAE, versioning, and market condition columns

Revision ID: 0005_v10_performance_journal
Revises: 0004_journal_strategy
Create Date: 2026-09-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_v10_performance_journal"
down_revision = "0004_journal_strategy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Execution
    op.add_column("trade_journal", sa.Column("fill_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column("trade_journal", sa.Column("fill_price", sa.Float(), nullable=True))

    # Realized performance
    op.add_column("trade_journal", sa.Column("realized_r_multiple", sa.Float(), nullable=True))

    # MFE / MAE tracking
    op.add_column("trade_journal", sa.Column("peak_price", sa.Float(), nullable=True))
    op.add_column("trade_journal", sa.Column("trough_price", sa.Float(), nullable=True))
    op.add_column("trade_journal", sa.Column("mfe_r", sa.Float(), nullable=True))
    op.add_column("trade_journal", sa.Column("mae_r", sa.Float(), nullable=True))

    # Strategy versioning
    op.add_column("trade_journal", sa.Column("strategy_version", sa.String(length=16), nullable=True))

    # Adaptive-rule versioning
    op.add_column("trade_journal", sa.Column("adaptive_rule_version", sa.String(length=16), nullable=True))
    op.add_column("trade_journal", sa.Column("adaptive_stop_multiplier", sa.Float(), nullable=True))

    # Market conditions at entry
    op.add_column("trade_journal", sa.Column("spread_at_entry", sa.Float(), nullable=True))
    op.add_column("trade_journal", sa.Column("atr_at_entry", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("trade_journal", "atr_at_entry")
    op.drop_column("trade_journal", "spread_at_entry")
    op.drop_column("trade_journal", "adaptive_stop_multiplier")
    op.drop_column("trade_journal", "adaptive_rule_version")
    op.drop_column("trade_journal", "strategy_version")
    op.drop_column("trade_journal", "mae_r")
    op.drop_column("trade_journal", "mfe_r")
    op.drop_column("trade_journal", "trough_price")
    op.drop_column("trade_journal", "peak_price")
    op.drop_column("trade_journal", "realized_r_multiple")
    op.drop_column("trade_journal", "fill_price")
    op.drop_column("trade_journal", "fill_time")
