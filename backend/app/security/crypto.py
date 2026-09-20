"""Symmetric encryption for OAuth tokens at rest.

Uses Fernet (AES-128-CBC + HMAC). The key comes from ``TOKEN_ENCRYPTION_KEY``.
If it is absent in development, a key is derived deterministically from
``SECRET_KEY`` so local dev works — but that is **rejected in production**.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import get_logger

logger = get_logger("app.security.crypto")

_fernet: Fernet | None = None


class EncryptionError(AppError):
    code = "encryption_error"
    http_status = 500
    message = "Could not process secure data."


def _derive_key() -> bytes:
    """Return a valid Fernet key.

    Priority: explicit TOKEN_ENCRYPTION_KEY, else derive from SECRET_KEY.
    """
    configured = settings.token_encryption_key
    if configured:
        key = configured.strip().encode()
        # Validate shape early.
        try:
            Fernet(key)
            return key
        except (ValueError, TypeError) as exc:  # pragma: no cover - config error
            raise EncryptionError("TOKEN_ENCRYPTION_KEY is not a valid Fernet key.") from exc

    if settings.is_production:
        raise EncryptionError("TOKEN_ENCRYPTION_KEY must be set in production.")

    # Development fallback: derive a stable key from the secret.
    digest = hashlib.sha256(settings.secret_key.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_derive_key())
    return _fernet


def encrypt(plaintext: str | None) -> str | None:
    """Encrypt a string; ``None`` passes through as ``None``."""
    if plaintext is None:
        return None
    return get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str | None) -> str | None:
    """Decrypt a string; returns ``None`` on empty/invalid input.

    Invalid tokens are logged (never surfaced raw) and treated as absent so a
    user simply sees "reconnect required".
    """
    if not ciphertext:
        return None
    try:
        return get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.warning("Failed to decrypt stored token (invalid or rotated key).")
        return None