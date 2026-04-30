"""
SAAB-SUITE — J2534 interface module.

Entry point:  python3 -m src.j2534.interface --test
Hardware:     Mongoose Pro GM II (J2534 pass-thru)
"""

import sys
import argparse


def test_interface() -> bool:
    """
    Probe for a J2534 DLL / device.
    On Windows this checks the registry for installed J2534 devices.
    On Linux/Termux this checks for a CANUSB or FTDI device node.
    """
    import platform
    os_name = platform.system()

    if os_name == "Windows":
        return _test_windows()
    else:
        return _test_posix()


def _test_windows() -> bool:
    try:
        import winreg
        key_path = r"SOFTWARE\PassThruSupport.04.04"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            i = 0
            devices = []
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    devices.append(subkey_name)
                    i += 1
                except OSError:
                    break
        if devices:
            print(f"[*] J2534 devices found: {devices}")
            return True
        else:
            print("[!] No J2534 devices registered")
            return False
    except FileNotFoundError:
        print("[!] J2534 registry key not found (no J2534 driver installed?)")
        return False
    except ImportError:
        print("[!] winreg not available on this platform")
        return False


def _test_posix() -> bool:
    import os
    candidates = [
        "/dev/ttyUSB0",
        "/dev/ttyUSB1",
        "/dev/ttyACM0",
        "/dev/ttyACM1",
    ]
    found = [d for d in candidates if os.path.exists(d)]
    if found:
        print(f"[*] Serial/USB device(s) found: {found}")
        return True
    print("[!] No serial/USB device found for J2534 (Mongoose disconnected?)")
    return False


def run(args: argparse.Namespace) -> None:
    if args.test:
        print("[*] src.j2534.interface — interface probe")
        ok = test_interface()
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="J2534 interface probe")
    parser.add_argument("--test", action="store_true", help="Run interface self-test")
    args = parser.parse_args()
    run(args)
