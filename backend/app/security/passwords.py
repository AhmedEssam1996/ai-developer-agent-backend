"""Password hashing and verification (bcrypt via passlib)."""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return _pwd_context.verify(plain_password, hashed_password)
    except ValueError:
        return False


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Basic strength policy. Returns ``(ok, reason)``."""
    if len(password) < 10:
        return False, "Password must be at least 10 characters."
    if password.lower() == password or password.upper() == password:
        return False, "Password must include upper and lower case letters."
    if not any(ch.isdigit() for ch in password):
        return False, "Password must include at least one number."
    return True, ""