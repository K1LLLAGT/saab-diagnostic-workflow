"""SAAB-SUITE cloud backend — DTC history / freeze frame / notes routes."""

from __future__ import annotations
import json
import time
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.auth import get_current_user, require_role
from backend.app.models import DTCHistoryEntry, FreezeFrame, TechnicianNote
from backend.app.schemas import DTCEntryIn, DTCEntryOut, NoteIn, NoteOut
from backend.app.crypto import encrypt_field, decrypt_field

router = APIRouter(tags=["dtc"])


@router.get("/vehicles/{vin}/dtc", response_model=List[DTCEntryOut])
def list_dtc_history(vin: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(DTCHistoryEntry).filter(DTCHistoryEntry.vin == vin).order_by(
        DTCHistoryEntry.recorded_at.desc()).all()
    return [
        DTCEntryOut(id=r.id, vin=r.vin, code=r.code, status=r.status,
                    payload=json.loads(r.payload or "{}"), recorded_at=r.recorded_at)
        for r in rows
    ]


@router.post("/vehicles/{vin}/dtc", response_model=DTCEntryOut)
def add_dtc_entry(vin: str, entry: DTCEntryIn, db: Session = Depends(get_db),
                   user=Depends(require_role("technician"))):
    row = DTCHistoryEntry(vin=vin, code=entry.code, status=entry.status,
                           payload=json.dumps(entry.payload), recorded_at=time.time())
    db.add(row)
    db.commit()
    db.refresh(row)
    return DTCEntryOut(id=row.id, vin=row.vin, code=row.code, status=row.status,
                        payload=entry.payload, recorded_at=row.recorded_at)


@router.get("/vehicles/{vin}/freeze-frames")
def list_freeze_frames(vin: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(FreezeFrame).filter(FreezeFrame.vin == vin).order_by(FreezeFrame.recorded_at.desc()).all()
    return [{"id": r.id, "dtc_code": r.dtc_code, "payload": json.loads(r.payload or "{}"),
             "recorded_at": r.recorded_at} for r in rows]


@router.get("/vehicles/{vin}/notes", response_model=List[NoteOut])
def list_notes(vin: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(TechnicianNote).filter(TechnicianNote.vin == vin).order_by(
        TechnicianNote.recorded_at.desc()).all()
    return [NoteOut(id=r.id, vin=r.vin, author=r.author, note=decrypt_field(r.note_encrypted),
                     recorded_at=r.recorded_at) for r in rows]


@router.post("/vehicles/{vin}/notes", response_model=NoteOut)
def add_note(vin: str, note: NoteIn, db: Session = Depends(get_db),
             user=Depends(require_role("technician"))):
    row = TechnicianNote(vin=vin, author=note.author, note_encrypted=encrypt_field(note.note),
                          recorded_at=time.time())
    db.add(row)
    db.commit()
    db.refresh(row)
    return NoteOut(id=row.id, vin=row.vin, author=row.author, note=note.note, recorded_at=row.recorded_at)
