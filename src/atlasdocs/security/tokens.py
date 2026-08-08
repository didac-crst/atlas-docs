"""Encrypt Paperless authorization material at rest (ADR 0002)."""

from __future__ import annotations

import base64
import hashlib
import secrets

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

DEFAULT_TOKEN_ENCRYPTION_KEY = "dev-only-token-encryption-key"


def token_fingerprint(authorization: str) -> str:
    return hashlib.sha256(authorization.encode("utf-8")).hexdigest()


def _fernet(secret: str) -> Fernet:
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"atlasdocs-v05-token-v1",
        info=b"paperless-authorization",
    ).derive(secret.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_token(plaintext: str, *, key: str) -> str:
    return _fernet(key).encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_token(ciphertext: str, *, key: str) -> str:
    try:
        return _fernet(key).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt token ciphertext") from exc


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def new_session_id() -> str:
    return secrets.token_urlsafe(32)
