"""SAAB-SUITE cloud backend — Pydantic request/response schemas."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class VINProfileOut(BaseModel):
    vin: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    payload: Dict[str, Any] = {}
    updated_at: float


class DTCEntryIn(BaseModel):
    code: str
    status: str = "active"
    payload: Dict[str, Any] = {}


class DTCEntryOut(DTCEntryIn):
    id: str
    vin: str
    recorded_at: float


class NoteIn(BaseModel):
    author: str
    note: str


class NoteOut(BaseModel):
    id: str
    vin: str
    author: str
    note: str
    recorded_at: float


class SyncRecordIn(BaseModel):
    payload: Dict[str, Any]
    client_updated_at: float


class SyncConflict(BaseModel):
    conflict: bool = True
    server_payload: Dict[str, Any]
    server_updated_at: float
