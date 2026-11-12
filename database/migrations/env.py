import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

try:
    from dotenv import load_dotenv
    # Only load .env if DATABASE_URL is not explicitly provided in the process environment
    if "DATABASE_URL" not in os.environ:
        load_dotenv(BACKEND_DIR / ".env")
except ImportError:
    pass

from app.core.database.models import Base  # noqa: E402
from app.core.database.migration_guard import validate_migration_target, redact_url  # noqa: E402
from app.core.database.session import normalize_database_url  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Require explicit environment and fail-closed validation against accidental production targets
migration_env = os.getenv("MIGRATION_ENV")
raw_database_url = os.getenv("DATABASE_URL")

validated_url = validate_migration_target(
    migration_env=migration_env,
    database_url=raw_database_url,
)

config.set_main_option("sqlalchemy.url", normalize_database_url(validated_url))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
