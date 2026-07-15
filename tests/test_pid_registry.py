from src.pid.registry import PIDRegistry, Mode


def test_rpm_decode():
    reg = PIDRegistry()
    d = reg.get(Mode.CURRENT_DATA, 0x0C)
    assert d is not None
    assert d.decode_value(bytes([0x1A, 0xF8])) == 1726.0


def test_coolant_temp_decode():
    reg = PIDRegistry()
    d = reg.get(Mode.CURRENT_DATA, 0x05)
    assert d.decode_value(bytes([0x5A])) == 0x5A - 40


def test_vin_pid_decode():
    reg = PIDRegistry()
    d = reg.get(Mode.VEHICLE_INFO, 0x02)
    assert d.decode_value(b"YS3FD45Y381234567") == "YS3FD45Y381234567"


def test_unknown_pid_returns_none():
    reg = PIDRegistry()
    assert reg.get(Mode.CURRENT_DATA, 0xFE) is None
    assert reg.decode(Mode.CURRENT_DATA, 0xFE, b"\x00") is None
