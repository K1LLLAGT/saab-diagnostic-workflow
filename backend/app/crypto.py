"""
SAAB-SUITE cloud backend — at-rest field encryption.

Symmetric encryption (Fernet/AES-128-CBC+HMAC) for sensitive free-text
fields (technician notes, chat transcripts). The key is read from
SAABSUITE_ENCRYPTION_KEY (base64 urlsafe, 32 bytes) — generate one with
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
and set it as an environment variable / secret. Never commit a real key.
"""

from __future__ import annotations
import base64
import os

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None  # encryption unavailable until `cryptography` is installed


_DEV_FALLBACK_KEY = base64.urlsafe_b64encode(b"0" * 32)  # dev-only, not for production


def _get_fernet():
    if Fernet is None:
        return None
    key = os.environ.get("SAABSUITE_ENCRYPTION_KEY", "").encode() or _DEV_FALLBACK_KEY
    return Fernet(key)


def encrypt_field(plaintext: str) -> str:
    f = _get_fernet()
    if f is None or not plaintext:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_field(ciphertext: str) -> str:
    f = _get_fernet()
    if f is None or not ciphertext:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        return "[decryption failed]"
