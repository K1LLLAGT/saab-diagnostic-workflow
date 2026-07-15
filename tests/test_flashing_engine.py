import pytest

from src.flashing.engine import FlashSession, FlashProtocol, FlashState, FlashSafeAbort, FlashBlock
from src.flashsafe.checklist import FlashSafeChecklist, VehicleState
from src.plugins.base import SeedKeyProvider, NullSeedKeyProvider


class _WorkingSeedKeyProvider(SeedKeyProvider):
    def compute_key(self, seed: bytes, level: int) -> bytes:
        return bytes((~b) & 0xFF for b in seed)


def _good_checklist() -> FlashSafeChecklist:
    state = VehicleState(
        battery_voltage=13.0, ignition_on=True, can_bus_stable=True,
        j2534_buffer_ok=True, programming_session_active=True,
        blocking_dtcs=[], calibration_file_valid=True,
    )
    checklist = FlashSafeChecklist()
    checklist.evaluate(state)
    return checklist


def test_flash_aborts_without_checklist_clear():
    bad_checklist = FlashSafeChecklist()
    bad_checklist.evaluate(VehicleState(battery_voltage=11.0))
    session = FlashSession(FlashProtocol.UDS_ISO14229, bad_checklist,
                            seed_key_provider=_WorkingSeedKeyProvider())
    with pytest.raises(FlashSafeAbort):
        session.start([FlashBlock(0, 0x1000, b"\xAA" * 16, 1)])


def test_flash_fails_closed_without_seed_key_provider():
    session = FlashSession(FlashProtocol.UDS_ISO14229, _good_checklist(),
                            seed_key_provider=NullSeedKeyProvider())
    with pytest.raises(RuntimeError):
        session.start([FlashBlock(0, 0x1000, b"\xAA" * 16, 1)])
    assert session.progress.state == FlashState.FAILED


def test_flash_completes_with_valid_provider():
    session = FlashSession(FlashProtocol.UDS_ISO14229, _good_checklist(),
                            seed_key_provider=_WorkingSeedKeyProvider())
    blocks = [FlashBlock(i, 0x1000 + i * 16, b"\xAA" * 16, 3) for i in range(3)]
    progress = session.start(blocks, resume=False)
    assert progress.state == FlashState.COMPLETE
    assert progress.blocks_sent == 3
    assert progress.percent == 100.0


def test_resume_from_checkpoint(tmp_path):
    checkpoint = tmp_path / "checkpoint.json"
    blocks = [FlashBlock(i, 0x1000 + i * 16, b"\xAA" * 16, 3) for i in range(3)]

    session1 = FlashSession(FlashProtocol.UDS_ISO14229, _good_checklist(),
                             seed_key_provider=_WorkingSeedKeyProvider(),
                             checkpoint_path=str(checkpoint))
    # Simulate a checkpoint left mid-way (as if a previous run crashed after block 1).
    checkpoint.write_text('{"next_block_index": 2}')

    session2 = FlashSession(FlashProtocol.UDS_ISO14229, _good_checklist(),
                             seed_key_provider=_WorkingSeedKeyProvider(),
                             checkpoint_path=str(checkpoint))
    progress = session2.start(blocks, resume=True)
    assert progress.blocks_sent == 1  # only block index 2 remained
    assert not checkpoint.exists()  # cleared on completion
