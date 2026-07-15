from src.cloud.sync import OfflineCache


def test_upsert_vin_profile_uses_vin_as_pk(tmp_path):
    cache = OfflineCache(str(tmp_path / "cache.sqlite3"))
    cache.upsert("vin_profiles", "YS3FD45Y381234567", "YS3FD45Y381234567",
                 {"make": "Saab", "model": "9-3 Aero XWD", "year": 2008})
    cur = cache._conn.execute("SELECT vin, payload FROM vin_profiles WHERE vin = ?",
                               ("YS3FD45Y381234567",))
    row = cur.fetchone()
    assert row is not None
    assert row[0] == "YS3FD45Y381234567"


def test_upsert_vin_profile_is_idempotent_on_conflict(tmp_path):
    cache = OfflineCache(str(tmp_path / "cache.sqlite3"))
    vin = "YS3FD45Y381234567"
    cache.upsert("vin_profiles", vin, vin, {"make": "Saab"})
    cache.upsert("vin_profiles", vin, vin, {"make": "Saab", "model": "9-3 Aero XWD"})
    cur = cache._conn.execute("SELECT COUNT(*) FROM vin_profiles WHERE vin = ?", (vin,))
    assert cur.fetchone()[0] == 1


def test_upsert_dtc_history_uses_id_pk_and_recorded_at(tmp_path):
    cache = OfflineCache(str(tmp_path / "cache.sqlite3"))
    cache.upsert("dtc_history", "dtc-1", "YS3FD45Y381234567",
                 {"code": "P0562"}, extra={"code": "P0562", "status": "active"})
    cur = cache._conn.execute("SELECT id, vin, code, status FROM dtc_history WHERE id = ?", ("dtc-1",))
    row = cur.fetchone()
    assert row == ("dtc-1", "YS3FD45Y381234567", "P0562", "active")


def test_pending_queue_grows_on_upsert(tmp_path):
    cache = OfflineCache(str(tmp_path / "cache.sqlite3"))
    cache.upsert("vin_profiles", "v1", "v1", {})
    cache.upsert("dtc_history", "d1", "v1", {}, extra={"code": "P0001", "status": "active"})
    assert len(cache.pending()) == 2
