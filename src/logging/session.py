"""
SAAB-SUITE — Session logger.

Creates a timestamped run directory and writes structured log entries.
"""

import os
import datetime
import pathlib


class SessionLogger:
    def __init__(self, root: str = "logs", prefix: str = "diag"):
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        self.run_dir = pathlib.Path(root) / f"{prefix}-{ts}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self.run_dir / "session.log"
        self._write_header()

    def _write_header(self) -> None:
        with open(self._log_path, "w") as f:
            f.write(f"=== SAAB-SUITE SESSION LOG ===\n")
            f.write(f"Started: {datetime.datetime.now().isoformat()}\n\n")

    def log(self, msg: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        with open(self._log_path, "a") as f:
            f.write(line + "\n")

    @property
    def path(self) -> pathlib.Path:
        return self.run_dir
