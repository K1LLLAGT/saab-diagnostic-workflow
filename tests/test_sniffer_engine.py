import time
from src.sniffer.engine import SnifferEngine, CANFrame


def test_capture_and_histogram():
    eng = SnifferEngine()
    eng.capture(CANFrame(arb_id=0x120, data=bytes([1, 2, 3])))
    eng.capture(CANFrame(arb_id=0x120, data=bytes([1, 2, 4])))
    eng.capture(CANFrame(arb_id=0x1A0, data=bytes([9, 9])))
    hist = eng.id_histogram()
    assert hist["0x120"] == 2
    assert hist["0x1A0"] == 1


def test_payload_diff_detected():
    eng = SnifferEngine()
    eng.capture(CANFrame(arb_id=0x120, data=bytes([1, 2, 3])))
    diff = eng.capture(CANFrame(arb_id=0x120, data=bytes([1, 9, 3])))
    assert diff is not None
    assert diff["changed_byte_indices"] == [1]


def test_filter_drops_frames():
    eng = SnifferEngine()
    eng.add_filter(lambda f: f.arb_id != 0x000)
    result = eng.capture(CANFrame(arb_id=0x000, data=bytes([0])))
    assert result is None
    assert len(eng.frames) == 0


def test_bitrate_detection_heuristic():
    eng = SnifferEngine()
    t0 = time.time()
    for i in range(20):
        eng.capture(CANFrame(arb_id=0x120, data=bytes([i]), timestamp=t0 + i * 0.001))
    rate = eng.detect_bitrate()
    assert rate == 500_000


def test_export_json(tmp_path):
    eng = SnifferEngine()
    eng.capture(CANFrame(arb_id=0x120, data=bytes([1, 2, 3])))
    out = tmp_path / "capture.json"
    eng.export_json(str(out))
    assert out.exists()
    assert "0x120" in out.read_text()


def test_export_log_and_asc(tmp_path):
    eng = SnifferEngine()
    eng.capture(CANFrame(arb_id=0x120, data=bytes([1, 2, 3])))
    log_path = tmp_path / "capture.log"
    asc_path = tmp_path / "capture.asc"
    eng.export_log(str(log_path))
    eng.export_asc(str(asc_path))
    assert log_path.exists() and asc_path.exists()
