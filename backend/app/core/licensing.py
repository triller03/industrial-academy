"""Offline license (blueprint: HWID licensing).

The desktop webview talks to a local ASAPA server. When a connection to the
platform is available the client pulls a signed offline-license JWT that binds
the user's plan to the hardware ids (HWIDs) it registers. That token keeps the
tiered features working for the full offline window (30-day trial / length of
paid license) exactly like the blueprint's offline SQLite promise.

Everything here is stateless except the DB rows that record purchases and
activation. The signed payload is verified with the same secret_key that signs
access tokens, so no extra key material needs to ship on the device.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from jose import JWTError, jwt

from app.config import get_settings
from app.models import User
from app.plans import plan_key, plan_label, trial_ends_at

LICENSE_TYPE = "license"


def new_license_key() -> str:
    """Human-pasteable 5x4 key, e.g. ASAPA-8F3K-Q2NW-P9XT-M7RC."""
    zone = [secrets.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(16)]
    groups = ["".join(zone[i : i + 4]) for i in range(0, 16, 4)]
    return "ASAPA-" + "-".join(groups)


def make_offline_license(
    user: User,
    hwids: list[str] | None = None,
    expires_at: datetime | None = None,
) -> str:
    """Sign a hardware-bound offline license token for the user's plan."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires = expires_at or trial_expiry(user)
    payload = {
        "sub": str(user.id),
        "typ": LICENSE_TYPE,
        "plan": plan_key(user),
        "plan_name": plan_label(plan_key(user)),
        "hwids": [h for h in (hwids or []) if h][: settings.device_limit_per_user],
        "iss": "asapa-license",
        "iat": now,
        "exp": expires,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def verify_offline_license(token: str) -> dict | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
    if payload.get("typ") != LICENSE_TYPE or payload.get("iss") != "asapa-license":
        return None
    if payload.get("exp") is None:
        return None
    return payload


def trial_expiry(user: User) -> datetime:
    return trial_ends_at(user)


def plan_expiry(days: int | None = None) -> datetime:
    from datetime import timedelta

    return datetime.now(timezone.utc) + timedelta(days=int(days or get_settings().license_length_days))


def public_origin() -> str:
    """Origin used for shareable public URLs, or '' when unknown (tests/local)."""
    return (get_settings().interface_origin or "").rstrip("/")