from src.calibration.catalog import CalibrationCatalog


def test_list_ecus_and_index():
    cat = CalibrationCatalog("calibrations")
    assert "T8" in cat.list_ecus()
    index = cat.index("T8")
    assert len(index) == 2


def test_get_record():
    cat = CalibrationCatalog("calibrations")
    record = cat.get("T8", "CAL0001")
    assert record is not None
    assert record.os_id == "E87-BASE"


def test_lookup_by_vin_prefix_match():
    cat = CalibrationCatalog("calibrations")
    matches = cat.lookup_by_vin("YS3FD45Y381234567")
    cal_ids = {m.cal_id for m in matches}
    assert "CAL0001" in cal_ids
    assert "CAL0002" in cal_ids


def test_dependency_resolution_order():
    cat = CalibrationCatalog("calibrations")
    order = cat.resolve_dependencies("T8", "CAL0002")
    assert order.index("CAL0001") < order.index("CAL0002")


def test_flash_compatibility_match_and_mismatch():
    cat = CalibrationCatalog("calibrations")
    ok = cat.check_flash_compatibility("T8", "CAL0001", "E87-BASE")
    assert ok["compatible"] is True
    bad = cat.check_flash_compatibility("T8", "CAL0001", "E87-OTHER")
    assert bad["compatible"] is False


def test_update_history_chain():
    cat = CalibrationCatalog("calibrations")
    history = cat.update_history("T8", "CAL0002")
    ids = [h["cal_id"] for h in history]
    assert ids == ["CAL0002", "CAL0001"]
