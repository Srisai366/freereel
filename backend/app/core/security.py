from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_hasher = PasswordHasher()
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


@lru_cache
def dummy_hash() -> str:
    """Hash checked when the username is unknown, so login timing doesn't reveal valid usernames."""
    return _hasher.hash("timing-equalizer-not-a-real-password")


def create_access_token(admin_id: int, role: str) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires_in = settings.jwt_expire_minutes * 60
    payload = {
        "sub": str(admin_id),
        "role": role,
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "typ": "admin",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM), expires_in


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError if the token is invalid, expired, or not an admin token."""
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[_ALGORITHM],
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iat", "sub", "iss"]},
    )
    if payload.get("typ") != "admin":
        raise jwt.InvalidTokenError("wrong token type")
    return payload
