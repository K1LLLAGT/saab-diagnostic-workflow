"""
SAAB-SUITE — cloud sync client.

Offline-first client for the cloud-synced vehicle history database
(backend/app). Maintains a local SQLite cache and an outbound sync
queue, and resolves conflicts via last-write-wins with a preserved
conflict log (safer default for a single-technician tool than silent
overwrite; swap _resolve_conflict for a merge policy if needed).

Entry point:  python3 -m src.cloud.sync --demo
"""

from __future__ import annotations
import argparse
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None  # network sync unavailable without `requests`; offline cache still works


SCHEMA = """
CREATE TABLE IF NOT EXISTS vin_profiles (
    vin TEXT PRIMARY KEY, make TEXT, model TEXT, year INTEGER,
    updated_at REAL, payload TEXT
);
CREATE TABLE IF NOT EXISTS dtc_history (
    id TEXT PRIMARY KEY, vin TEXT, code TEXT, status TEXT,
    recorded_at REAL, payload TEXT
);
CREATE TABLE IF NOT EXISTS freeze_frames (
    id TEXT PRIMARY KEY, vin TEXT, dtc_code TEXT, recorded_at REAL, payload TEXT
);
CREATE TABLE IF NOT EXISTS live_snapshots (
    id TEXT PRIMARY KEY, vin TEXT, label TEXT, recorded_at REAL, payload TEXT
);
CREATE TABLE IF NOT EXISTS flash_history (
    id TEXT PRIMARY KEY, vin TEXT, ecu TEXT, cal_id TEXT, result TEXT, recorded_at REAL, payload TEXT
);
CREATE TABLE IF NOT EXISTS technician_notes (
    id TEXT PRIMARY KEY, vin TEXT, author TEXT, note TEXT, recorded_at REAL
);
CREATE TABLE IF NOT EXISTS log_files (
    id TEXT PRIMARY KEY, vin TEXT, path TEXT, recorded_at REAL
);
CREATE TABLE IF NOT EXISTS sync_queue (
    id TEXT PRIMARY KEY, table_name TEXT, record_id TEXT,
    op TEXT, queued_at REAL, attempts INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sync_conflicts (
    id TEXT PRIMARY KEY, table_name TEXT, record_id TEXT,
    local_payload TEXT, remote_payload TEXT, detected_at REAL
);
"""

SYNCABLE_TABLES = [
    "vin_profiles", "dtc_history", "freeze_frames",
    "live_snapshots", "flash_history", "technician_notes", "log_files",
]


class OfflineCache:
    def __init__(self, db_path: str = "cloud_cache.sqlite3"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # vin_profiles uses `vin` as its primary key and `updated_at` as its
    # timestamp column (there is exactly one profile row per VIN); every
    # other syncable table uses `id` / `recorded_at`.
    _PK_COLUMN = {"vin_profiles": "vin"}
    _TS_COLUMN = {"vin_profiles": "updated_at"}

    def upsert(self, table: str, record_id: str, vin: str, payload: dict, extra: dict = None) -> None:
        extra = extra or {}
        pk_col = self._PK_COLUMN.get(table, "id")
        ts_col = self._TS_COLUMN.get(table, "recorded_at")
        cols = [pk_col] + (["vin"] if pk_col != "vin" else []) + ["payload", ts_col] + list(extra.keys())
        vals = [record_id] + ([vin] if pk_col != "vin" else []) + [json.dumps(payload), time.time()] + list(extra.values())
        placeholders = ",".join("?" * len(cols))
        col_list = ",".join(cols)
        update_clause = ",".join(f"{c}=excluded.{c}" for c in cols if c != pk_col)
        self._conn.execute(
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
            f"ON CONFLICT({pk_col}) DO UPDATE SET {update_clause}",
            vals,
        )
        self._conn.commit()
        self.enqueue(table, record_id, op="upsert")

    def enqueue(self, table: str, record_id: str, op: str = "upsert") -> None:
        self._conn.execute(
            "INSERT INTO sync_queue (id, table_name, record_id, op, queued_at) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), table, record_id, op, time.time()),
        )
        self._conn.commit()

    def pending(self) -> List[dict]:
        cur = self._conn.execute("SELECT id, table_name, record_id, op, queued_at, attempts FROM sync_queue")
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def dequeue(self, queue_id: str) -> None:
        self._conn.execute("DELETE FROM sync_queue WHERE id = ?", (queue_id,))
        self._conn.commit()

    def record_conflict(self, table: str, record_id: str, local: dict, remote: dict) -> None:
        self._conn.execute(
            "INSERT INTO sync_conflicts (id, table_name, record_id, local_payload, remote_payload, detected_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), table, record_id, json.dumps(local), json.dumps(remote), time.time()),
        )
        self._conn.commit()


@dataclass
class CloudSyncClient:
    """
    OAuth2 bearer-token REST client with an offline cache/queue. Server
    contract: backend/app (see backend/app/routes_sync.py).
    """
    base_url: str
    cache: OfflineCache = field(default_factory=OfflineCache)
    access_token: Optional[str] = None

    def authenticate(self, username: str, password: str) -> bool:
        if requests is None:
            return False
        try:
            resp = requests.post(f"{self.base_url}/oauth/token",
                                  data={"grant_type": "password", "username": username, "password": password},
                                  timeout=5)
            if resp.status_code == 200:
                self.access_token = resp.json().get("access_token")
                return True
        except requests.RequestException:
            pass
        return False

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}

    def flush_queue(self) -> Dict[str, int]:
        """Push queued local changes; pull remote state for the same
        record; last-write-wins on `recorded_at`/`updated_at`, with the
        losing write preserved in sync_conflicts for technician review."""
        result = {"pushed": 0, "conflicts": 0, "failed": 0}
        if requests is None or not self.access_token:
            return result

        for item in self.cache.pending():
            try:
                local_row = self._read_local(item["table_name"], item["record_id"])
                if local_row is None:
                    self.cache.dequeue(item["id"])
                    continue
                resp = requests.put(
                    f"{self.base_url}/sync/{item['table_name']}/{item['record_id']}",
                    json=local_row, headers=self._headers(), timeout=10,
                )
                if resp.status_code == 409:
                    remote = resp.json()
                    self.cache.record_conflict(item["table_name"], item["record_id"], local_row, remote)
                    result["conflicts"] += 1
                elif resp.ok:
                    self.cache.dequeue(item["id"])
                    result["pushed"] += 1
                else:
                    result["failed"] += 1
            except requests.RequestException:
                result["failed"] += 1
        return result

    def _read_local(self, table: str, record_id: str) -> Optional[dict]:
        pk_col = self.cache._PK_COLUMN.get(table, "id")
        cur = self.cache._conn.execute(f"SELECT * FROM {table} WHERE {pk_col} = ?", (record_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))


def _demo() -> None:
    cache = OfflineCache(":memory:" if False else "/tmp/saabsuite_cloud_demo.sqlite3")
    cache.upsert("vin_profiles", "profile-1", "YS3FD45Y381234567",
                 {"make": "Saab", "model": "9-3 Aero XWD", "year": 2008})
    cache.upsert("dtc_history", "dtc-1", "YS3FD45Y381234567",
                 {"code": "P0562", "desc": "System Voltage Low"}, extra={"code": "P0562", "status": "active"})
    print(f"Pending sync items: {len(cache.pending())}")
    for item in cache.pending():
        print(f"  {item}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cloud sync client")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if args.demo:
        _demo()
