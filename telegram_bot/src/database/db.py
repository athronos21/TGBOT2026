"""
Database engine and session management.

The engine is created lazily on first use so that tests can override
DATABASE_URL (or swap the engine entirely) before any DB call is made.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.database.models import Base

# These are module-level variables that tests (and conftest.py) can replace
# before any session is opened.
engine = None
SessionLocal = None


def _ensure_engine() -> None:
    """Initialise engine and SessionLocal on first call."""
    global engine, SessionLocal
    if engine is None:
        from src.config import DATABASE_URL
        engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Create all tables if they don't exist."""
    _ensure_engine()
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a transactional database session."""
    _ensure_engine()
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
