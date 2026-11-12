"""
Unit tests for Falcon staging configuration and deployment safety.

Verifies:
1. fly.staging.toml format, app name ('falcon-api-staging'), region, health checks,
   and safety flags (EXECUTION_MODE=PAPER, LIVE_EXECUTION_ACKNOWLEDGED=False, OANDA_AUTO_EXECUTE=False).
2. fly.staging.toml contains zero plaintext secrets or database credentials.
3. .dockerignore strictly blocks .env, *.db, and credentials from build context.
4. validate_migration_target correctly authorizes dedicated staging database URLs with MIGRATION_ENV=STAGING.
5. validate_migration_target strictly rejects production Supabase and ambiguous targets under MIGRATION_ENV=STAGING.
6. Alembic migration graph has single linear head strictly at 0008_v10_initial_stop_loss.
"""

from pathlib import Path
import pytest

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.database.migration_guard import (
    validate_migration_target,
    MigrationTargetError,
    ALLOWED_ENVIRONMENTS,
)


def test_fly_staging_toml_exists_and_is_valid():
    """Verify fly.staging.toml exists and is valid TOML."""
    toml_path = Path(__file__).resolve().parents[2] / "fly.staging.toml"
    assert toml_path.exists(), "backend/fly.staging.toml must exist"

    with open(toml_path, "rb") as f:
        data = tomllib.load(f)

    assert data.get("app") == "falcon-api-staging"
    assert data.get("primary_region") == "lhr"

    env = data.get("env", {})
    assert env.get("PORT") == "8000"
    assert env.get("EXECUTION_MODE") == "PAPER"
    assert env.get("LIVE_EXECUTION_ACKNOWLEDGED") == "False"
    assert env.get("OANDA_AUTO_EXECUTE") == "False"
    assert env.get("MIGRATION_ENV") == "STAGING"

    http_service = data.get("http_service", {})
    assert http_service.get("internal_port") == 8000

    checks = http_service.get("checks", [])
    assert len(checks) >= 1
    assert checks[0].get("path") == "/api/v1/health"


def test_fly_staging_toml_contains_no_secrets():
    """Verify fly.staging.toml does not contain DATABASE_URL or sensitive tokens."""
    toml_path = Path(__file__).resolve().parents[2] / "fly.staging.toml"
    content = toml_path.read_text(encoding="utf-8")

    forbidden_keywords = [
        "DATABASE_URL",
        "supabase",
        "password",
        "secret",
        "oanda_api_key",
        "fmp_api_key",
        "jwt_secret",
    ]
    for kw in forbidden_keywords:
        assert kw not in content.lower(), f"Forbidden credential keyword '{kw}' found in fly.staging.toml"


def test_dockerignore_excludes_sensitive_files():
    """Verify .dockerignore excludes .env and sqlite databases."""
    dockerignore_path = Path(__file__).resolve().parents[2] / ".dockerignore"
    assert dockerignore_path.exists()
    content = dockerignore_path.read_text(encoding="utf-8")

    assert ".env" in content
    assert "*.db" in content or "*.sqlite" in content


def test_migration_guard_authorizes_valid_staging_url():
    """MIGRATION_ENV=STAGING accepts a valid staging Fly Postgres URL."""
    staging_url = "postgresql+psycopg://falcon_user:test_secret@falcon-staging-db.internal:5432/falcon_staging"
    validated = validate_migration_target("STAGING", staging_url)
    assert validated == staging_url


def test_migration_guard_rejects_production_supabase_in_staging():
    """MIGRATION_ENV=STAGING strictly rejects any production Supabase URL."""
    prod_url = "postgresql+psycopg://postgres:secret@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
    with pytest.raises(MigrationTargetError) as exc_info:
        validate_migration_target("STAGING", prod_url)
    assert "production or shared cloud host" in str(exc_info.value).lower()


def test_migration_guard_rejects_ambiguous_url_in_staging():
    """MIGRATION_ENV=STAGING rejects URLs without 'stage', 'staging', 'test', or 'dev' keyword."""
    ambiguous_url = "postgresql+psycopg://user:pass@internal-pg.internal:5432/my_database"
    with pytest.raises(MigrationTargetError) as exc_info:
        validate_migration_target("STAGING", ambiguous_url)
    assert "must explicitly identify as staging" in str(exc_info.value).lower()


def test_alembic_head_matches_0008():
    """Verify Alembic migration head is strictly 0008_v10_initial_stop_loss."""
    ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(ini_path))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert heads == ["0008_v10_initial_stop_loss"]
