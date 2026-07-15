"""
SAAB-SUITE cloud backend — database setup.

SQLite by default (single-technician / small-fleet deployment); set
DATABASE_URL to point at Postgres etc. for a multi-user deployment.
Sensitive columns (technician_notes.note) are stored via
app.crypto.encrypt_field — see that module for the at-rest encryption
approach used for "encrypted storage".
"""

from __future__ import annotations
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("SAABSUITE_DATABASE_URL", "sqlite:///./saabsuite_cloud.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from backend.app import models  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(bind=engine)
