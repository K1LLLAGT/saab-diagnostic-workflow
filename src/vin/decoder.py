"""
SAAB-SUITE — VIN decoder (ISO 3779 / SAE J853 structure).

Decodes WMI (World Manufacturer Identifier), validates the ISO 3779 check
digit, and derives model year from the VIS. This module implements only
the publicly standardized VIN structure — it does not decode manufacturer
-proprietary VDS option/trim segments beyond what OEM plugins supply via
`decode_vds()` hooks (see src/plugins/base.py: OEMPlugin.decode_vds).

Entry point:  python3 -m src.vin.decoder YS3FD45Y381234567
"""

from __future__ import annotations
import argparse
import sys
from dataclasses import dataclass, field
from typing import Optional, Dict


_TRANSLITERATION = {
    **{c: v for c, v in zip("ABCDEFGH", [1, 2, 3, 4, 5, 6, 7, 8])},
    **{c: v for c, v in zip("JKLMNPRSTUVWXYZ", [1, 2, 3, 4, 5, 7, 9, 2, 3, 4, 5, 6, 7, 8, 9])},
    **{str(d): d for d in range(10)},
}

_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]

_YEAR_CODES = {
    "A": 2010, "B": 2011, "C": 2012, "D": 2013, "E": 2014, "F": 2015,
    "G": 2016, "H": 2017, "J": 2018, "K": 2019, "L": 2020, "M": 2021,
    "N": 2022, "P": 2023, "R": 2024, "S": 2025, "T": 2026, "V": 2027,
    "W": 2028, "X": 2029, "Y": 2030,
    "1": 2001, "2": 2002, "3": 2003, "4": 2004, "5": 2005, "6": 2006,
    "7": 2007, "8": 2008, "9": 2009,
}

# WMI prefixes for a handful of common manufacturers used across this suite
# and its OEM plugins. Extend via plugin manifests (see plugins/*/manifest.json).
_WMI_TABLE: Dict[str, str] = {
    "YS3": "Saab Automobile AB (Sweden)",
    "1G1": "General Motors — Chevrolet (USA)",
    "1G6": "General Motors — Cadillac (USA)",
    "1GC": "General Motors — Chevrolet Truck (USA)",
    "1GM": "General Motors — Pontiac (USA)",
    "1FA": "Ford Motor Company (USA)",
    "1FT": "Ford Motor Company — Truck (USA)",
    "3FA": "Ford Motor Company (Mexico)",
    "WBA": "BMW AG (Germany)",
    "WVW": "Volkswagen AG (Germany)",
}


@dataclass
class DecodedVIN:
    vin: str
    valid: bool
    wmi: str
    manufacturer: str
    vds: str
    vis: str
    model_year: Optional[int]
    check_digit_expected: str
    check_digit_actual: str
    errors: list = field(default_factory=list)


def validate_check_digit(vin: str) -> tuple[bool, str]:
    """ISO 3779 / NHTSA check-digit algorithm (position 9)."""
    if len(vin) != 17:
        return False, "?"
    total = 0
    for i, ch in enumerate(vin.upper()):
        val = _TRANSLITERATION.get(ch)
        if val is None:
            return False, "?"
        total += val * _WEIGHTS[i]
    remainder = total % 11
    expected = "X" if remainder == 10 else str(remainder)
    return expected == vin[8].upper(), expected


def decode(vin: str) -> DecodedVIN:
    vin = (vin or "").strip().upper()
    errors = []

    if len(vin) != 17:
        errors.append(f"VIN must be 17 characters (got {len(vin)})")
    if any(c in vin for c in "IOQ"):
        errors.append("VIN contains disallowed characters I, O, or Q")

    wmi = vin[0:3] if len(vin) >= 3 else ""
    vds = vin[3:9] if len(vin) >= 9 else ""
    vis = vin[9:17] if len(vin) >= 17 else ""

    valid_chk, expected = (False, "?")
    actual = vin[8] if len(vin) >= 9 else "?"
    if not errors:
        valid_chk, expected = validate_check_digit(vin)
        if not valid_chk:
            errors.append(f"Check digit mismatch: expected '{expected}', got '{actual}'")

    year = None
    if len(vin) >= 10:
        year = _YEAR_CODES.get(vin[9])
        if year is None:
            errors.append(f"Unrecognized model-year code '{vin[9]}'")

    manufacturer = _WMI_TABLE.get(wmi, "Unknown manufacturer (WMI not in local table)")

    return DecodedVIN(
        vin=vin,
        valid=(len(errors) == 0),
        wmi=wmi,
        manufacturer=manufacturer,
        vds=vds,
        vis=vis,
        model_year=year,
        check_digit_expected=expected,
        check_digit_actual=actual,
        errors=errors,
    )


def run(args: argparse.Namespace) -> None:
    result = decode(args.vin)
    print(f"VIN:            {result.vin}")
    print(f"Valid:          {result.valid}")
    print(f"WMI:            {result.wmi}  ({result.manufacturer})")
    print(f"VDS:            {result.vds}")
    print(f"VIS:            {result.vis}")
    print(f"Model year:     {result.model_year}")
    print(f"Check digit:    expected='{result.check_digit_expected}' actual='{result.check_digit_actual}'")
    if result.errors:
        print("Errors:")
        for e in result.errors:
            print(f"  - {e}")
    sys.exit(0 if result.valid else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Decode a VIN (ISO 3779)")
    parser.add_argument("vin", help="17-character VIN")
    run(parser.parse_args())
