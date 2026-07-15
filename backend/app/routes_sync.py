"""
SAAB-SUITE cloud backend — sync endpoints for src.cloud.sync.CloudSyncClient.

Conflict policy: if the client's payload is older than the server's
current `updated_at`/`recorded_at`, respond 409 with the server's
current record so the client can log it via OfflineCache.record_conflict
instead of blindly overwriting newer server data.
"""

from __future__ import annotations
import json
import time
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.auth import require_role
from backend.app import models

router = APIRouter(prefix="/sync", tags=["sync"])

_TABLE_MODEL = {
    "vin_profiles": (models.VINProfile, "vin", "updated_at"),
    "dtc_history": (models.DTCHistoryEntry, "id", "recorded_at"),
    "freeze_frames": (models.FreezeFrame, "id", "recorded_at"),
    "live_snapshots": (models.LiveSnapshot, "id", "recorded_at"),
    "flash_history": (models.FlashHistoryEntry, "id", "recorded_at"),
    "log_files": (models.LogFileRef, "id", "recorded_at"),
}


@router.put("/{table}/{record_id}")
def sync_upsert(table: str, record_id: str, body: Dict[str, Any],
                 db: Session = Depends(get_db), user=Depends(require_role("technician"))):
    if table not in _TABLE_MODEL:
        raise HTTPException(status_code=404, detail=f"Unknown sync table '{table}'")
    model, pk_field, ts_field = _TABLE_MODEL[table]

    row = db.query(model).filter(getattr(model, pk_field) == record_id).first()
    client_ts = body.get(ts_field, 0)

    if row is not None and getattr(row, ts_field, 0) > client_ts:
        return _conflict_response(row, ts_field)

    if row is None:
        row = model(**{pk_field: record_id})
        db.add(row)

    for key, value in body.items():
        if hasattr(row, key) and key != pk_field:
            setattr(row, key, json.dumps(value) if isinstance(value, (dict, list)) else value)
    setattr(row, ts_field, time.time())
    db.commit()
    return {"status": "synced", "record_id": record_id}


def _conflict_response(row, ts_field: str):
    from fastapi.responses import JSONResponse
    payload = {c.name: getattr(row, c.name) for c in row.__table__.columns}
    return JSONResponse(status_code=409, content={
        "conflict": True, "server_payload": payload, "server_updated_at": getattr(row, ts_field),
    })
