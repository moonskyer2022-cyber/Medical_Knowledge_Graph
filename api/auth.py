"""Small dependency-free bearer-token authentication for controlled demos."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass


class AuthenticationError(ValueError):
    """Raised when a bearer token or credential is invalid."""


@dataclass(frozen=True)
class AuthUser:
    username: str
    roles: tuple[str, ...]


def authentication_enabled() -> bool:
    return os.getenv("AUTH_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def _secret() -> bytes:
    value = os.getenv("AUTH_SECRET", "")
    if len(value) < 32:
        raise AuthenticationError("AUTH_SECRET must contain at least 32 characters when authentication is enabled")
    return value.encode("utf-8")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def verify_credentials(username: str, password: str) -> AuthUser:
    expected_username = os.getenv("AUTH_DEMO_USERNAME", "")
    expected_password = os.getenv("AUTH_DEMO_PASSWORD", "")
    if not expected_username or not expected_password:
        raise AuthenticationError("demo credentials are not configured")
    if not hmac.compare_digest(username, expected_username) or not hmac.compare_digest(password, expected_password):
        raise AuthenticationError("invalid username or password")
    roles = tuple(role.strip() for role in os.getenv("AUTH_DEMO_ROLES", "clinician").split(",") if role.strip())
    return AuthUser(username=username, roles=roles or ("clinician",))


def issue_token(user: AuthUser) -> str:
    now = int(time.time())
    ttl = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "3600"))
    payload = {"sub": user.username, "roles": list(user.roles), "iat": now, "exp": now + ttl}
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64encode(hmac.new(_secret(), encoded_payload.encode("ascii"), hashlib.sha256).digest())
    return f"v1.{encoded_payload}.{signature}"


def decode_token(token: str) -> AuthUser:
    try:
        version, encoded_payload, encoded_signature = token.split(".")
        expected_signature = hmac.new(_secret(), encoded_payload.encode("ascii"), hashlib.sha256).digest()
        if version != "v1" or not hmac.compare_digest(_b64decode(encoded_signature), expected_signature):
            raise AuthenticationError("invalid token signature")
        payload = json.loads(_b64decode(encoded_payload))
        if not isinstance(payload.get("sub"), str) or int(payload.get("exp", 0)) <= int(time.time()):
            raise AuthenticationError("expired or malformed token")
        roles = payload.get("roles", [])
        if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
            raise AuthenticationError("malformed token roles")
        return AuthUser(username=payload["sub"], roles=tuple(roles))
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        if isinstance(exc, AuthenticationError):
            raise
        raise AuthenticationError("malformed token") from exc


def user_from_authorization(header: str | None) -> AuthUser:
    if not header or not header.startswith("Bearer "):
        raise AuthenticationError("missing bearer token")
    return decode_token(header.removeprefix("Bearer ").strip())
