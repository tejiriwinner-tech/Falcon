"""Target environment validation and migration safety guard for Falcon.

Prevents routine, local, test, or staging migrations from accidentally
connecting to or mutating production infrastructure.
"""

import os
from typing import Optional
from urllib.parse import urlsplit, urlunsplit


class MigrationTargetError(RuntimeError):
    """Raised when an invalid, ambiguous, or forbidden migration target is detected."""
    pass


ALLOWED_ENVIRONMENTS = ("LOCAL", "TEST", "DISPOSABLE", "STAGING")

# Hostname fragments that identify production or shared cloud environments
KNOWN_PRODUCTION_HOST_PATTERNS = (
    "supabase.co",
    "supabase.com",
    "pooler.supabase.com",
    "cockroachlabs.cloud",
    "rds.amazonaws.com",
)

# Known production hostnames configured for Falcon
KNOWN_PRODUCTION_HOSTS = (
    "aws-0-eu-west-1.pooler.supabase.com",
    "aws-0-eu-west-2.pooler.supabase.com",
)


def redact_url(url: Optional[str]) -> str:
    """Safely redact credentials (passwords) from database URLs for logging and error reporting."""
    if not url:
        return "<EMPTY>"
    try:
        parts = urlsplit(url)
        if parts.password:
            # Reconstruct netloc with redacted password
            user = parts.username or ""
            host = parts.hostname or ""
            port = f":{parts.port}" if parts.port else ""
            userinfo = f"{user}:[REDACTED]" if user else "[REDACTED]"
            netloc = f"{userinfo}@{host}{port}"
            return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
        return url
    except Exception:
        return "<UNPARSEABLE_URL>"


def validate_migration_target(
    migration_env: Optional[str],
    database_url: Optional[str],
) -> str:
    """Validates the migration target against the explicit migration environment.

    Requirements:
    1. An explicit environment ('LOCAL', 'TEST', 'DISPOSABLE', 'STAGING') is required.
    2. 'PRODUCTION' is strictly rejected on evaluation branches.
    3. Missing or ambiguous environments fail closed.
    4. Database URL must be provided and must match the authorized constraints of the environment:
       - LOCAL: Must point to localhost, 127.0.0.1, host.docker.internal, or sqlite.
       - TEST / DISPOSABLE: Must be sqlite or a designated isolated test database name.
       - STAGING: Must explicitly be designated staging, and must not match production hosts.
    5. Passwords and credentials must never appear in error messages.

    Returns:
        The validated database URL string.

    Raises:
        MigrationTargetError: If the environment or target fails validation.
    """
    env_clean = (migration_env or "").strip().upper()

    if not env_clean:
        raise MigrationTargetError(
            "MIGRATION_ENV is unset. Falcon migrations require an explicit environment "
            "('LOCAL', 'TEST', 'DISPOSABLE', 'STAGING') to prevent accidental database mutations."
        )

    if env_clean == "PRODUCTION":
        raise MigrationTargetError(
            "Production migrations are strictly forbidden on evaluation branch 'real-data-work'. "
            "Production Fly.io release v11 (commit 1a7e57b) remains frozen."
        )

    if env_clean not in ALLOWED_ENVIRONMENTS:
        raise MigrationTargetError(
            f"Invalid MIGRATION_ENV '{env_clean}'. Allowed environments are: {', '.join(ALLOWED_ENVIRONMENTS)}."
        )

    if not database_url or not str(database_url).strip():
        raise MigrationTargetError("DATABASE_URL is not set.")

    raw_url = str(database_url).strip()
    safe_display_url = redact_url(raw_url)

    try:
        parsed = urlsplit(raw_url)
    except Exception as ex:
        raise MigrationTargetError(f"DATABASE_URL could not be parsed: {ex}")

    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()

    # 1. Check for production signatures
    is_prod_host = any(pattern in host for pattern in KNOWN_PRODUCTION_HOST_PATTERNS) or (host in KNOWN_PRODUCTION_HOSTS)
    
    if is_prod_host:
        raise MigrationTargetError(
            f"Target validation failed: DATABASE_URL points to a production or shared cloud host '{host}'. "
            f"Migrations against production-like hosts are prohibited under MIGRATION_ENV='{env_clean}'. "
            f"Target: {safe_display_url}"
        )

    # 2. Validate environment constraints
    if env_clean in ("TEST", "DISPOSABLE"):
        is_sqlite = scheme in ("sqlite", "sqlite+aiosqlite")
        is_named_test = any(kw in path for kw in ("test", "disposable", "mock", "temp")) or any(kw in host for kw in ("test", "disposable"))
        if not (is_sqlite or is_named_test):
            raise MigrationTargetError(
                f"Target validation failed for MIGRATION_ENV='{env_clean}': Target must be an in-memory/file "
                f"SQLite database or a database explicitly designated with 'test' or 'disposable'. "
                f"Target: {safe_display_url}"
            )

    elif env_clean == "LOCAL":
        is_sqlite = scheme in ("sqlite", "sqlite+aiosqlite")
        is_local_host = host in ("localhost", "127.0.0.1", "::1", "host.docker.internal")
        if not (is_sqlite or is_local_host):
            raise MigrationTargetError(
                f"Target validation failed for MIGRATION_ENV='LOCAL': Local migrations must target "
                f"localhost, 127.0.0.1, or SQLite. Remote host '{host}' is prohibited. "
                f"Target: {safe_display_url}"
            )

    elif env_clean == "STAGING":
        is_staging_designated = any(kw in host or kw in path for kw in ("stage", "staging", "test", "dev"))
        if not is_staging_designated:
            raise MigrationTargetError(
                f"Target validation failed for MIGRATION_ENV='STAGING': Database URL host or path must "
                f"explicitly identify as staging. Ambiguous target rejected. "
                f"Target: {safe_display_url}"
            )

    return raw_url
