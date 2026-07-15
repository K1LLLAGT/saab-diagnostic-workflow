from src.vin.decoder import decode, validate_check_digit


def test_decode_wrong_length():
    result = decode("SHORTVIN")
    assert not result.valid
    assert any("17 characters" in e for e in result.errors)


def test_decode_saab_wmi_recognized():
    # Structurally valid length/charset VIN with the Saab WMI, check digit
    # not asserted here (see test_check_digit_math for the algorithm itself).
    result = decode("YS3FD45Y381234567")
    assert result.wmi == "YS3"
    assert "Saab" in result.manufacturer
    assert result.model_year == 2008  # '8' -> 2008


def test_check_digit_math_self_consistent():
    # Build a VIN, compute its expected check digit, substitute it in,
    # and confirm validate_check_digit reports it valid.
    base = list("YS3FD45Y0812345XX")[:17]
    base[8] = "0"
    vin = "".join(base)
    valid, expected = validate_check_digit(vin)
    base[8] = expected
    fixed_vin = "".join(base)
    valid2, _ = validate_check_digit(fixed_vin)
    assert valid2 is True


def test_disallowed_characters():
    result = decode("YS3FD45Y3I1234567")  # contains 'I'
    assert not result.valid
    assert any("disallowed" in e for e in result.errors)
