"""
SAAB-SUITE — Analysis module.

Entry point:  python3 -m src.analysis.analyzer
Responsibility: environment validation + diagnostic data analysis.
"""

import sys
import platform


def check_environment() -> bool:
    """Validate Python version and basic runtime environment."""
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 8):
        print(f"[!] Python 3.8+ required (found {major}.{minor})")
        return False
    print(f"[*] Python {major}.{minor}: OK")
    print(f"[*] Platform: {platform.system()} {platform.release()}")
    return True


def run() -> None:
    print("[*] src.analysis.analyzer — environment check")
    ok = check_environment()
    if not ok:
        sys.exit(1)
    print("[*] Analysis module ready.")


if __name__ == "__main__":
    run()
