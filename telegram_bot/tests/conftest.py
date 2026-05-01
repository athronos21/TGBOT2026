"""
Shared pytest fixtures.

Uses an in-memory SQLite database so tests run without Postgres or psycopg2.
db.py now uses lazy engine init, so we inject a SQLite engine before any
test code calls get_session() or init_db().
"""
import sys
import os

# Ensure telegram_bot/ root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set env vars before any src module is imported
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_TELEGRAM_ID", "0")
os.environ.setdefault("DB_PASSWORD", "test")

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

# Import models first (safe — no engine needed)
from src.database.models import Base, TimeSlot
import src.database.db as _db_module
from src.config import DAYS, HOURS


def _make_sqlite_engine():
    """Create a fresh in-memory SQLite engine with FK enforcement."""
    eng = create_engine("sqlite:///:memory:", echo=False)

    @event.listens_for(eng, "connect")
    def set_fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return eng


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def engine():
    """
    Fresh in-memory SQLite engine per test.
    Also patches db.py so get_session() uses this engine.
    """
    eng = _make_sqlite_engine()
    Base.metadata.create_all(eng)

    # Inject into db module so commands.py → get_session() uses SQLite
    _db_module.engine = eng
    _db_module.SessionLocal = sessionmaker(bind=eng, autocommit=False, autoflush=False)

    yield eng

    Base.metadata.drop_all(eng)
    eng.dispose()
    # Reset so next test gets a fresh engine
    _db_module.engine = None
    _db_module.SessionLocal = None


@pytest.fixture(scope="function")
def session(engine) -> Session:
    """Transactional session bound to the test engine."""
    sess = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    yield sess
    sess.rollback()
    sess.close()


@pytest.fixture
def seeded_slots(session) -> int:
    """Seed all Mon–Fri 08:00–17:00 time slots and return count added."""
    added = 0
    for day in DAYS:
        for hour in HOURS:
            session.add(TimeSlot(day=day, start_hour=hour, end_hour=hour + 1))
            added += 1
    session.flush()
    return added
