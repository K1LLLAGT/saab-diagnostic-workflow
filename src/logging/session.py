"""
SAAB-SUITE — VIN-tagged session logger.

Each diagnostic run creates a structured directory:

  logs/
    <VIN>/
      <YYYYMMDD-HHMM>-<prefix>/
        session.json   ← machine-readable structured log
        session.log    ← human-readable plaintext log

session.json schema:
  {
    "vin":       "YS3FD45Y381234567",
    "prefix":    "diag",
    "started":   "2024-01-15T14:32:00",
    "ended":     null,
    "host":      "kali-rog",
    "entries":   [
      {"ts": "14:32:00.123", "level": "INFO", "msg": "..."},
      ...
    ],
    "summary":   { "errors": 0, "warnings": 0, "dtc_count": 0 }
  }
"""

from __future__ import annotations
import json
import os
import platform
import datetime
import pathlib
import logging
from typing import List, Dict, Any, Optional


class SessionLogger:
    """
    VIN-tagged, JSON + plaintext session logger.

    Usage:
        log = SessionLogger(vin="YS3FD45Y381234567", prefix="diag")
        log.info("Connected to T8")
        log.warning("J2534 probe failed")
        log.finalize(dtc_count=3)
    """

    DEFAULT_VIN = "UNKNOWN_VIN"

    def __init__(self, vin: str = DEFAULT_VIN,
                 prefix: str = "diag",
                 root: str = "logs"):
        self.vin    = vin.strip().upper() or self.DEFAULT_VIN
        self.prefix = prefix
        ts          = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        self.run_dir = pathlib.Path(root) / self.vin / f"{ts}-{prefix}"
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self._log_path  = self.run_dir / "session.log"
        self._json_path = self.run_dir / "session.json"

        self._entries: List[Dict[str, Any]] = []
        self._errors   = 0
        self._warnings = 0

        self._session: Dict[str, Any] = {
            "vin":     self.vin,
            "prefix":  self.prefix,
            "started": datetime.datetime.now().isoformat(timespec="seconds"),
            "ended":   None,
            "host":    platform.node(),
            "entries": self._entries,
            "summary": {},
        }

        self._write_json()
        self.info(f"Session started — VIN: {self.vin}  host: {platform.node()}")

    # ── Public logging API ────────────────────────────────────────────────────

    def info(self, msg: str) -> None:
        self._append("INFO", msg)

    def warning(self, msg: str) -> None:
        self._warnings += 1
        self._append("WARN", msg)

    def error(self, msg: str) -> None:
        self._errors += 1
        self._append("ERROR", msg)

    def data(self, label: str, value: Any) -> None:
        self._append("DATA", f"{label} = {value}")

    # ── Finalise ──────────────────────────────────────────────────────────────

    def finalize(self, dtc_count: int = 0) -> None:
        self._session["ended"] = datetime.datetime.now().isoformat(timespec="seconds")
        self._session["summary"] = {
            "errors":    self._errors,
            "warnings":  self._warnings,
            "dtc_count": dtc_count,
        }
        self._write_json()
        self.info(
            f"Session ended — errors={self._errors} "
            f"warnings={self._warnings} dtcs={dtc_count}"
        )

    # ── Path helpers ──────────────────────────────────────────────────────────

    @property
    def path(self) -> pathlib.Path:
        return self.run_dir

    @property
    def json_path(self) -> pathlib.Path:
        return self._json_path

    # ── Internal ──────────────────────────────────────────────────────────────

    def _append(self, level: str, msg: str) -> None:
        ts   = datetime.datetime.now().strftime("%H:%M:%S.%f")[:12]
        line = f"[{ts}] [{level:5s}] {msg}"
        print(line)
        with open(self._log_path, "a") as f:
            f.write(line + "\n")
        self._entries.append({"ts": ts, "level": level, "msg": msg})
        self._write_json()

    def _write_json(self) -> None:
        with open(self._json_path, "w") as f:
            json.dump(self._session, f, indent=2)
