"""Create price history and economic calendar tables

Revision ID: 0003_market_data
Revises: 0002_trade_journal
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_market_data"
down_revision = "0002_trade_journal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("bar_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "symbol",
            "timeframe",
            "bar_time",
            name="uq_price_history_symbol_timeframe_bar_time",
        ),
    )
    op.create_index(
        "ix_price_history_symbol_timeframe", "price_history", ["symbol", "timeframe"]
    )

    op.create_table(
        "economic_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("impact", sa.String(length=16), nullable=False),
        sa.Column("forecast", sa.String(length=64), nullable=True),
        sa.Column("previous", sa.String(length=64), nullable=True),
        sa.Column("actual", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_time",
            "currency",
            "title",
            name="uq_economic_events_time_currency_title",
        ),
    )
    op.create_index("ix_economic_events_event_time", "economic_events", ["event_time"])


def downgrade() -> None:
    op.drop_index("ix_economic_events_event_time", table_name="economic_events")
    op.drop_table("economic_events")
    op.drop_index("ix_price_history_symbol_timeframe", table_name="price_history")
    op.drop_table("price_history")
