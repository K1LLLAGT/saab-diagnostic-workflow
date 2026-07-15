"""SAAB-SUITE cloud backend — vehicle / VIN profile routes."""

from __future__ import annotations
import json
import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.auth import get_current_user, require_role
from backend.app.models import VINProfile, LiveSnapshot, FlashHistoryEntry
from backend.app.schemas import VINProfileOut

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("", response_model=List[VINProfileOut])
def list_vehicles(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(VINProfile).all()
    return [
        VINProfileOut(vin=r.vin, make=r.make, model=r.model, year=r.year,
                       payload=json.loads(r.payload or "{}"), updated_at=r.updated_at)
        for r in rows
    ]


@router.get("/{vin}", response_model=VINProfileOut)
def get_vehicle(vin: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = db.query(VINProfile).filter(VINProfile.vin == vin).first()
    if not row:
        raise HTTPException(status_code=404, detail="VIN profile not found")
    return VINProfileOut(vin=row.vin, make=row.make, model=row.model, year=row.year,
                          payload=json.loads(row.payload or "{}"), updated_at=row.updated_at)


@router.put("/{vin}", response_model=VINProfileOut)
def upsert_vehicle(vin: str, profile: dict, db: Session = Depends(get_db),
                    user=Depends(require_role("technician"))):
    row = db.query(VINProfile).filter(VINProfile.vin == vin).first()
    if not row:
        row = VINProfile(vin=vin)
        db.add(row)
    row.make = profile.get("make", row.make)
    row.model = profile.get("model", row.model)
    row.year = profile.get("year", row.year)
    row.payload = json.dumps(profile.get("payload", {}))
    row.updated_at = time.time()
    db.commit()
    db.refresh(row)
    return VINProfileOut(vin=row.vin, make=row.make, model=row.model, year=row.year,
                          payload=json.loads(row.payload or "{}"), updated_at=row.updated_at)


@router.get("/{vin}/snapshots")
def list_snapshots(vin: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(LiveSnapshot).filter(LiveSnapshot.vin == vin).order_by(LiveSnapshot.recorded_at.desc()).all()
    return [{"id": r.id, "label": r.label, "payload": json.loads(r.payload or "{}"),
             "recorded_at": r.recorded_at} for r in rows]


@router.get("/{vin}/flash-history")
def list_flash_history(vin: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(FlashHistoryEntry).filter(FlashHistoryEntry.vin == vin).order_by(
        FlashHistoryEntry.recorded_at.desc()).all()
    return [{"id": r.id, "ecu": r.ecu, "cal_id": r.cal_id, "result": r.result,
             "recorded_at": r.recorded_at} for r in rows]
