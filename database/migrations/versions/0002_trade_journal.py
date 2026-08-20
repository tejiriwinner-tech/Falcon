"""Create trade journal table and mission number sequence

Revision ID: 0002_trade_journal
Revises: 0001_mission_repository
Create Date: 2026-08-20

"""

import sqlalchemy as sa
from alembic import op

revision = "0002_trade_journal"
down_revision = "0001_mission_repository"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trade_journal",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("signal_id", sa.BigInteger(), nullable=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("stop_loss", sa.Float(), nullable=False),
        sa.Column("take_profit", sa.Float(), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("market_session", sa.String(length=32), nullable=False),
        sa.Column("trade_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("profit_loss", sa.Float(), nullable=False),
        sa.Column("risk_reward", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("reason_for_entry", sa.Text(), nullable=False),
        sa.Column("reason_for_exit", sa.Text(), nullable=True),
        sa.Column("lesson_learned", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trade_journal_trade_date", "trade_journal", ["trade_date"])

    # Mission numbers are allocated by the database so concurrent pipeline runs
    # cannot mint duplicate ids. Start after the highest number already stored.
    op.execute("CREATE SEQUENCE IF NOT EXISTS mission_number_seq AS BIGINT START 1")
    op.execute(
        """
        SELECT setval(
            'mission_number_seq',
            COALESCE(
                (
                    SELECT MAX(CAST(SUBSTRING(id FROM 'mission-([0-9]+)$') AS BIGINT))
                    FROM missions
                    WHERE id ~ '^mission-[0-9]+$'
                ),
                0
            ) + 1,
            false
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS mission_number_seq")
    op.drop_index("ix_trade_journal_trade_date", table_name="trade_journal")
    op.drop_table("trade_journal")
