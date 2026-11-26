"""Database engine/session setup. SQLite by default; set DATABASE_URL for PostgreSQL."""
from __future__ import annotations

import warnings
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.exc import SAWarning
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import BACKEND_DIR, get_settings

# SQLite stores NUMERIC as text/real; SQLAlchemy warns about Decimal round-trips.
# Values are quantized in the service layer, and PostgreSQL handles NUMERIC natively.
warnings.filterwarnings("ignore", category=SAWarning, message=".*Decimal objects natively.*")


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    connect_args = {}
    if url.startswith("sqlite"):
        (BACKEND_DIR / "data").mkdir(exist_ok=True)
        connect_args = {"check_same_thread": False}
    engine = create_engine(url, connect_args=connect_args, future=True)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _fk_pragma(dbapi_conn, _):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    return engine


engine = _make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    from . import models  # noqa: F401  (register models)

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
