"""Authentication primitives for ResQShield.

Provides:
- Argon2 password hashing
- JWT access tokens
- TOTP MFA helpers
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pyotp
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from backend.app.config import get_settings


_password_hash = PasswordHash.recommended()


class AuthenticationError(ValueError):
    """Raised when an authentication token is invalid or unusable."""


def hash_password(password: str) -> str:
    """Hash a plaintext password using the recommended Argon2 configuration."""

    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")

    return _password_hash.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against its stored Argon2 hash."""

    return _password_hash.verify(plain_password, password_hash)


def create_access_token(
    *,
    subject: str,
    role: str,
    mfa_verified: bool = False,
    expires_minutes: int | None = None,
) -> str:
    """Create a signed JWT access token."""

    settings = get_settings()

    lifetime = (
        expires_minutes
        if expires_minutes is not None
        else settings.access_token_expire_minutes
    )

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=lifetime)

    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "mfa": mfa_verified,
        "type": "access",
        "iat": now,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a ResQShield JWT access token."""

    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except InvalidTokenError as exc:
        raise AuthenticationError("Invalid or expired access token.") from exc

    if payload.get("type") != "access":
        raise AuthenticationError("Token is not an access token.")

    if not payload.get("sub"):
        raise AuthenticationError("Token subject is missing.")

    if not payload.get("role"):
        raise AuthenticationError("Token role is missing.")

    return payload


def generate_mfa_secret() -> str:
    """Generate a new TOTP secret for a user."""

    return pyotp.random_base32()


def build_mfa_provisioning_uri(*, secret: str, account_name: str) -> str:
    """Build a QR-compatible TOTP provisioning URI."""

    settings = get_settings()

    return pyotp.TOTP(secret).provisioning_uri(
        name=account_name,
        issuer_name=settings.mfa_issuer,
    )


def verify_mfa_code(*, secret: str, code: str) -> bool:
    """Verify a TOTP MFA code.

    valid_window=1 tolerates one adjacent 30-second interval for clock drift.
    """

    return pyotp.TOTP(secret).verify(code, valid_window=1)
