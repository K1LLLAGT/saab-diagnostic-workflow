"""SAAB-SUITE cloud backend — ORM models."""

from __future__ import annotations
import time
import uuid
from sqlalchemy import Column, String, Float, Integer, Text
from backend.app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uuid)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="technician")  # technician | lead | admin | readonly


class VINProfile(Base):
    __tablename__ = "vin_profiles"
    vin = Column(String, primary_key=True)
    make = Column(String)
    model = Column(String)
    year = Column(Integer)
    payload = Column(Text)          # JSON blob of extended profile data
    updated_at = Column(Float, default=time.time)


class DTCHistoryEntry(Base):
    __tablename__ = "dtc_history"
    id = Column(String, primary_key=True, default=_uuid)
    vin = Column(String, index=True)
    code = Column(String)
    status = Column(String)
    payload = Column(Text)
    recorded_at = Column(Float, default=time.time)


class FreezeFrame(Base):
    __tablename__ = "freeze_frames"
    id = Column(String, primary_key=True, default=_uuid)
    vin = Column(String, index=True)
    dtc_code = Column(String)
    payload = Column(Text)
    recorded_at = Column(Float, default=time.time)


class LiveSnapshot(Base):
    __tablename__ = "live_snapshots"
    id = Column(String, primary_key=True, default=_uuid)
    vin = Column(String, index=True)
    label = Column(String)
    payload = Column(Text)
    recorded_at = Column(Float, default=time.time)


class FlashHistoryEntry(Base):
    __tablename__ = "flash_history"
    id = Column(String, primary_key=True, default=_uuid)
    vin = Column(String, index=True)
    ecu = Column(String)
    cal_id = Column(String)
    result = Column(String)
    payload = Column(Text)
    recorded_at = Column(Float, default=time.time)


class TechnicianNote(Base):
    __tablename__ = "technician_notes"
    id = Column(String, primary_key=True, default=_uuid)
    vin = Column(String, index=True)
    author = Column(String)
    note_encrypted = Column(Text)
    recorded_at = Column(Float, default=time.time)


class LogFileRef(Base):
    __tablename__ = "log_files"
    id = Column(String, primary_key=True, default=_uuid)
    vin = Column(String, index=True)
    path = Column(String)
    recorded_at = Column(Float, default=time.time)
