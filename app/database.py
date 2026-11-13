from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from .models import Base


def make_engine(url: str):
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    eng = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        @event.listens_for(eng, "connect")
        def _fk(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(eng)
    return eng


def make_session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)
