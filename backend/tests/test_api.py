"""
SAAB-SUITE cloud backend — API tests.

Run:  pytest backend/tests/test_api.py
"""

from __future__ import annotations
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.app import db as db_module
from backend.app.main import app


@pytest.fixture()
def client():
    """Point db.py's module-level SessionLocal/engine at a fresh temp
    sqlite file for this test, since get_db() resolves SessionLocal from
    db.py's module globals at call time — patching it here is enough
    without re-importing the app (whose routers already hold references
    to get_db)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    test_engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    test_session_local = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    db_module.engine = test_engine
    db_module.SessionLocal = test_session_local

    from backend.app import models  # noqa: F401 — register models on Base
    db_module.Base.metadata.create_all(bind=test_engine)

    with TestClient(app) as c:
        yield c

    os.unlink(path)


def _register_and_login(client, username="tech1", password="hunter2pass"):
    resp = client.post("/oauth/register", data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_register_and_login(client):
    headers = _register_and_login(client)
    assert "Authorization" in headers


def test_vehicle_upsert_and_get(client):
    headers = _register_and_login(client)
    vin = "YS3FD45Y381234567"
    resp = client.put(f"/vehicles/{vin}",
                       json={"make": "Saab", "model": "9-3 Aero XWD", "year": 2008, "payload": {}},
                       headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["vin"] == vin

    resp = client.get(f"/vehicles/{vin}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["make"] == "Saab"


def test_dtc_history_roundtrip(client):
    headers = _register_and_login(client)
    vin = "YS3FD45Y381234567"
    resp = client.post(f"/vehicles/{vin}/dtc", json={"code": "P0562", "status": "active", "payload": {}},
                        headers=headers)
    assert resp.status_code == 200, resp.text

    resp = client.get(f"/vehicles/{vin}/dtc", headers=headers)
    assert resp.status_code == 200
    codes = [e["code"] for e in resp.json()]
    assert "P0562" in codes


def test_notes_are_encrypted_at_rest(client):
    headers = _register_and_login(client)
    vin = "YS3FD45Y381234567"
    resp = client.post(f"/vehicles/{vin}/notes", json={"author": "tech1", "note": "secret note"},
                        headers=headers)
    assert resp.status_code == 200
    assert resp.json()["note"] == "secret note"

    from backend.app.models import TechnicianNote
    db = db_module.SessionLocal()
    row = db.query(TechnicianNote).filter(TechnicianNote.vin == vin).first()
    assert row.note_encrypted != "secret note"
    db.close()


def test_requires_auth(client):
    resp = client.get("/vehicles")
    assert resp.status_code == 401
