from src.flashsafe.checklist import FlashSafeChecklist, VehicleState, CheckStatus


def _good_state() -> VehicleState:
    return VehicleState(
        battery_voltage=13.0, ignition_on=True, can_bus_stable=True,
        j2534_buffer_ok=True, programming_session_active=True,
        blocking_dtcs=[], calibration_file_valid=True,
    )


def test_all_clear_when_everything_good():
    checklist = FlashSafeChecklist()
    checklist.evaluate(_good_state())
    assert checklist.all_clear() is True
    assert checklist.failures() == []


def test_low_battery_blocks():
    state = _good_state()
    state.battery_voltage = 12.1
    checklist = FlashSafeChecklist()
    checklist.evaluate(state)
    assert checklist.all_clear() is False
    names = [r.name for r in checklist.failures()]
    assert "battery_voltage" in names


def test_ignition_off_blocks():
    state = _good_state()
    state.ignition_on = False
    checklist = FlashSafeChecklist()
    checklist.evaluate(state)
    assert checklist.all_clear() is False


def test_blocking_dtc_present():
    state = _good_state()
    state.blocking_dtcs = ["U0100"]
    checklist = FlashSafeChecklist()
    checklist.evaluate(state)
    assert checklist.all_clear() is False
    failure = next(r for r in checklist.failures() if r.name == "blocking_dtcs")
    assert "U0100" in failure.detail


def test_non_blocking_dtc_does_not_block():
    state = _good_state()
    state.blocking_dtcs = ["P0300"]  # random misfire code, not in blocking prefixes
    checklist = FlashSafeChecklist()
    checklist.evaluate(state)
    assert checklist.all_clear() is True


def test_unknown_reading_is_unknown_not_pass():
    state = VehicleState()  # everything None except blocking_dtcs, which defaults to []
    checklist = FlashSafeChecklist()
    results = checklist.evaluate(state)
    non_dtc_results = [r for r in results if r.name != "blocking_dtcs"]
    assert all(r.status == CheckStatus.UNKNOWN for r in non_dtc_results)
    assert checklist.all_clear() is False
