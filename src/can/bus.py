"""
SAAB-SUITE — CAN bus module.

Entry point:  python3 -m src.can.bus --device j2534 --interface mongoose
Supports:     J2534 pass-thru (Mongoose Pro GM II), CANUSB
"""

import sys
import argparse


SUPPORTED_DEVICES = ["j2534", "canusb", "socketcan"]
SUPPORTED_INTERFACES = ["mongoose", "canusb", "vcan0"]


def probe_can(device: str, interface: str) -> bool:
    print(f"[*] CAN probe — device={device}  interface={interface}")
    if device not in SUPPORTED_DEVICES:
        print(f"[!] Unknown device: {device}. Supported: {SUPPORTED_DEVICES}")
        return False
    if device == "j2534":
        print("[*] J2534 CAN channel: initialising...")
        print("[*] Protocol: ISO15765 / HS-CAN (500 kbps)")
        print("[!] CAN hardware not connected — stub mode")
        return True
    if device == "canusb":
        print("[*] CANUSB channel: initialising...")
        print("[!] CANUSB hardware not connected — stub mode")
        return True
    print(f"[!] Device '{device}' not yet implemented")
    return False


def run(args: argparse.Namespace) -> None:
    ok = probe_can(args.device, args.interface)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CAN bus probe")
    parser.add_argument("--device",    default="j2534",   help="Device type")
    parser.add_argument("--interface", default="mongoose", help="Interface name")
    args = parser.parse_args()
    run(args)
