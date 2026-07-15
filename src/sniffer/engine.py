"""
SAAB-SUITE — CAN-bus sniffer engine.

Raw frame capture, timestamping, bitrate detection heuristics, ID
grouping, payload diffing, filters, and export to .log / .asc / .json.

Entry point:  python3 -m src.sniffer.engine --demo
"""

from __future__ import annotations
import argparse
import json
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class CANFrame:
    arb_id: int
    data: bytes
    timestamp: float = field(default_factory=time.time)
    channel: str = "CAN1"
    extended: bool = False

    def to_dict(self) -> dict:
        return {
            "id": f"0x{self.arb_id:03X}",
            "data": self.data.hex().upper(),
            "dlc": len(self.data),
            "ts": self.timestamp,
            "channel": self.channel,
            "extended": self.extended,
        }


@dataclass
class IDStats:
    arb_id: int
    count: int = 0
    first_seen: float = 0.0
    last_seen: float = 0.0
    last_payload: Optional[bytes] = None
    intervals_ms: List[float] = field(default_factory=list)

    @property
    def avg_interval_ms(self) -> float:
        return sum(self.intervals_ms) / len(self.intervals_ms) if self.intervals_ms else 0.0

    @property
    def approx_hz(self) -> float:
        return round(1000.0 / self.avg_interval_ms, 2) if self.avg_interval_ms else 0.0


class SnifferEngine:
    """
    Usage:
        eng = SnifferEngine()
        eng.add_filter(lambda f: f.arb_id != 0x000)   # drop noise ID
        eng.capture(frame)
        eng.export_json("capture.json")
    """

    def __init__(self) -> None:
        self.frames: List[CANFrame] = []
        self._filters: List[Callable[[CANFrame], bool]] = []
        self._id_stats: Dict[int, IDStats] = {}
        self.detected_bitrate: Optional[int] = None

    # ── Filters ──────────────────────────────────────────────────────────

    def add_filter(self, predicate: Callable[[CANFrame], bool]) -> None:
        """Filter returns True to KEEP a frame."""
        self._filters.append(predicate)

    def clear_filters(self) -> None:
        self._filters.clear()

    def _passes_filters(self, frame: CANFrame) -> bool:
        return all(f(frame) for f in self._filters)

    # ── Capture ──────────────────────────────────────────────────────────

    def capture(self, frame: CANFrame) -> Optional[dict]:
        """Ingest a frame. Returns a payload-diff dict if the payload
        changed since the last frame with the same arb_id, else None."""
        if not self._passes_filters(frame):
            return None

        self.frames.append(frame)
        stats = self._id_stats.setdefault(frame.arb_id, IDStats(frame.arb_id))

        diff = None
        if stats.last_payload is not None and stats.last_payload != frame.data:
            diff = self._diff_payload(stats.last_payload, frame.data)

        if stats.count > 0:
            interval_ms = (frame.timestamp - stats.last_seen) * 1000.0
            stats.intervals_ms.append(interval_ms)
        else:
            stats.first_seen = frame.timestamp

        stats.count += 1
        stats.last_seen = frame.timestamp
        stats.last_payload = frame.data

        return diff

    @staticmethod
    def _diff_payload(old: bytes, new: bytes) -> dict:
        changed_bytes = [
            i for i in range(min(len(old), len(new))) if old[i] != new[i]
        ]
        return {
            "old": old.hex().upper(),
            "new": new.hex().upper(),
            "changed_byte_indices": changed_bytes,
        }

    # ── Bitrate detection heuristic ─────────────────────────────────────────
    # Real bitrate detection requires bus-level bit timing; this heuristic
    # infers a likely bitrate bucket from observed inter-frame spacing,
    # which is sufficient to flag HS-CAN (500k) vs MS-CAN/LS-CAN (125k/33.3k).

    def detect_bitrate(self) -> Optional[int]:
        if len(self.frames) < 10:
            return None
        deltas = [
            (self.frames[i].timestamp - self.frames[i - 1].timestamp) * 1000.0
            for i in range(1, len(self.frames))
        ]
        avg = sum(deltas) / len(deltas) if deltas else 0
        if avg <= 2:
            self.detected_bitrate = 500_000
        elif avg <= 8:
            self.detected_bitrate = 250_000
        elif avg <= 20:
            self.detected_bitrate = 125_000
        else:
            self.detected_bitrate = 33_300
        return self.detected_bitrate

    # ── Aggregates for UI (ID histogram / activity overview) ───────────────

    def id_histogram(self) -> Dict[str, int]:
        return {f"0x{arb_id:03X}": s.count for arb_id, s in sorted(self._id_stats.items())}

    def activity_overview(self) -> dict:
        return {
            "total_frames": len(self.frames),
            "unique_ids": len(self._id_stats),
            "detected_bitrate": self.detected_bitrate,
            "duration_s": (self.frames[-1].timestamp - self.frames[0].timestamp) if self.frames else 0,
            "top_ids": sorted(
                (
                    {"id": f"0x{s.arb_id:03X}", "count": s.count, "hz": s.approx_hz}
                    for s in self._id_stats.values()
                ),
                key=lambda x: -x["count"],
            )[:10],
        }

    def payload_heatmap(self, arb_id: int) -> List[List[int]]:
        """Per-byte-position value distribution for one arbitration ID —
        rows are frames, columns are byte positions."""
        return [list(f.data) for f in self.frames if f.arb_id == arb_id]

    # ── Export ───────────────────────────────────────────────────────────

    def export_json(self, path: str) -> None:
        with open(path, "w") as fh:
            json.dump([f.to_dict() for f in self.frames], fh, indent=2)

    def export_log(self, path: str) -> None:
        """Simple candump-style .log export: `timestamp channel id#data`."""
        with open(path, "w") as fh:
            for f in self.frames:
                fh.write(f"({f.timestamp:.6f}) {f.channel} {f.arb_id:03X}#{f.data.hex().upper()}\n")

    def export_asc(self, path: str) -> None:
        """Vector ASC-style export (simplified, single-channel)."""
        with open(path, "w") as fh:
            fh.write("date " + time.strftime("%a %b %d %I:%M:%S.000 %p %Y") + "\n")
            fh.write("base hex  timestamps absolute\n")
            fh.write("internal events logged\n")
            fh.write("Begin Triggerblock\n")
            for f in self.frames:
                dlc = len(f.data)
                data_str = " ".join(f"{b:02X}" for b in f.data)
                fh.write(f"{f.timestamp:.6f} 1  {f.arb_id:X}             Rx   d {dlc} {data_str}\n")
            fh.write("End TriggerBlock\n")

    # ── Filter profile save/load ────────────────────────────────────────────

    def save_filter_profile(self, path: str, id_allowlist: List[int]) -> None:
        with open(path, "w") as fh:
            json.dump({"id_allowlist": [f"0x{i:03X}" for i in id_allowlist]}, fh, indent=2)

    def load_filter_profile(self, path: str) -> None:
        with open(path) as fh:
            profile = json.load(fh)
        allowed = {int(x, 16) for x in profile.get("id_allowlist", [])}
        if allowed:
            self.add_filter(lambda f: f.arb_id in allowed)


def _demo() -> None:
    import random
    eng = SnifferEngine()
    ids = [0x120, 0x1A0, 0x280, 0x7E8]
    t0 = time.time()
    for i in range(50):
        arb_id = random.choice(ids)
        data = bytes([random.randint(0, 255) for _ in range(8)])
        eng.capture(CANFrame(arb_id=arb_id, data=data, timestamp=t0 + i * 0.01))
    eng.detect_bitrate()
    print(json.dumps(eng.activity_overview(), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CAN sniffer engine")
    parser.add_argument("--demo", action="store_true", help="Run a demo capture")
    args = parser.parse_args()
    if args.demo:
        _demo()
