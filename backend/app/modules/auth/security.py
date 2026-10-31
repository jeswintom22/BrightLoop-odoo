"""Password hashing (stdlib pbkdf2), policy validation, reset tokens, JWT.

Password rule note (audit §P1): the team task allocation says "minimum 8
characters" while the original problem statement says "more than 8" — we
enforce the STRICTER rule (MIN_LENGTH = 9, i.e. > 8) plus one uppercase,
one lowercase, one special character.
"""

import hashlib
import hmac
import re
import secrets
import datetime as dt

import jwt
from pydantic import field_validator

from ...core.config import get_settings
from ...core.time import utc_now

MIN_PASSWORD_LENGTH = 9  # original spec: "> 8 characters" (stricter than "min 8")
_SPECIAL = re.compile(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]")
_ITERATIONS = 200_000


def validate_password_rules(password: str) -> str:
    """Shared validator used by register/reset schemas. Returns the password."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be more than 8 characters (>= {MIN_PASSWORD_LENGTH})"
        )
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain an uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain a lowercase letter")
    if not _SPECIAL.search(password):
        raise ValueError("Password must contain a special character")
    return password


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), _ITERATIONS
    ).hex()
    return f"pbkdf2${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, digest = stored.split("$", 3)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iters)
        ).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, AttributeError):
        return False


def new_reset_token() -> tuple[str, str]:
    """Returns (raw_token, sha256_hex). Only the hash is persisted."""
    raw = secrets.token_urlsafe(32)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_token(user) -> str:
    """JWT consumed by deps.get_current_user — claims {sub, email, roles, exp}."""
    settings = get_settings()
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "roles": [user.role],
        "iat": utc_now(),
        "exp": utc_now() + dt.timedelta(hours=12),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
