"""
Falcon Database Configuration
SQLAlchemy database setup for historical market data storage.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config.settings import settings
import os

# Database URL - SQLite for development, can be changed to PostgreSQL for production
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "sqlite:///./falcon_market_data.db"
)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]

# Create engine with connection pooling for PostgreSQL
if "postgresql" in DATABASE_URL or "postgres" in DATABASE_URL or "supabase" in DATABASE_URL:
    # PostgreSQL/Supabase connection pool configuration
    # Keep pool minimal (2-3 connections) so Fly.io multi-worker machines do not exhaust Supabase pooler
    engine = create_engine(
        DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=600,
        pool_timeout=settings.DB_CONNECT_TIMEOUT,
        connect_args={"connect_timeout": settings.DB_CONNECT_TIMEOUT},
        echo=settings.DB_ECHO
    )
else:
    # SQLite configuration with optimizations
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=settings.DB_ECHO,
        # SQLite-specific optimizations
        pool_pre_ping=True,
        pool_recycle=3600
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
