"""Database engine and session management.

Falcon persists mission artifacts in Postgres (Supabase). When no
``DATABASE_URL`` is configured the application falls back to in-memory
storage so local development keeps working without a database.
"""

from typing import Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker[Session]] = None


def database_enabled() -> bool:
    return bool(settings.DATABASE_URL)


def normalize_database_url(url: str) -> str:
    """Return a URL using the psycopg (v3) driver expected by SQLAlchemy."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        if not settings.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured")
        _engine = create_engine(
            normalize_database_url(settings.DATABASE_URL),
            echo=settings.DB_ECHO,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            connect_args={"connect_timeout": settings.DB_CONNECT_TIMEOUT},
        )
    return _engine


def get_session_factory() -> "sessionmaker[Session]":
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory


def get_session() -> Session:
    return get_session_factory()()
