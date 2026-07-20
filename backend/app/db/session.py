"""SQLAlchemy engine, session factory, and FastAPI dependency."""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import normalize_database_url, settings


def build_engine(database_url: str | None = None) -> Engine:
    url = normalize_database_url(database_url or settings.DATABASE_URL)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield one transaction-capable session for a FastAPI request."""
    with SessionLocal() as session:
        yield session
