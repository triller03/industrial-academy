"""Tiered plans & feature gates (blueprint: monetization).

Free Sandbox keeps the full learning content and offline-first experience open —
that is the product promise. Money-gated surface is intentionally *additive* so
nobody is left without a working lab:

  sandbox        -> fault-lab daily cap, no public portfolio, no TIA bridge,
                    no learner project generation, no full-solution mentor.
  student_pro    -> unlimited fault attempts, learner project generation,
                    full-solution mentor, FRS/P&ID viewer, schematic data.
  professional   -> + public portfolio URL, + TIA Openness / SCL validator bridge.
  institutional  -> everything plus admin visibility (enforced in routes).

Plan rank comparisons keep the gate logic readable and testable.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ActivityLog, User

PLAN_ORDER = ["sandbox", "student_pro", "professional", "institutional"]

PLANS: dict[str, dict] = {
    "sandbox": {
        "name": "Free Sandbox",
        "price_usd": "Free",
        "trial_days": 30,
        "bullets": [
            "All authored projects (17-section lifecycle)",
            "Offline bundles + 90-day offline sync",
            "Graded Fault Lab (daily cap, then upgrade)",
            "30-day device license trial",
            "Standard AI mentor (Socratic, 5 tiers)",
        ],
    },
    "student_pro": {
        "name": "Student Pro",
        "price_usd": "$15",
        "bullets": [
            "Unlimited Fault Lab attempts",
            "Generate your own projects from templates",
            "AI mentor full-solution mode",
            "FRS & P&ID split viewer",
            "Priority support",
        ],
    },
    "professional": {
        "name": "Professional",
        "price_usd": "$39",
        "bullets": [
            "Everything in Student Pro",
            "Public portfolio URL (shareable work sample)",
            "TIA Openness bridge + SCL pre-compile validator",
            "Priority device slots",
        ],
    },
    "institutional": {
        "name": "Institutional",
        "price_usd": "Quote",
        "bullets": [
            "Everything in Professional",
            "Bulk seats + admin console",
            "On-site TIA Portal integration support",
            "Dedicated onboarding & curriculum mapping",
        ],
    },
}


def as_aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; normalise them to UTC rather than mixing."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def plan_key(user: User | None) -> str:
    """Resolve a user's effective plan key (admin climbs to institutional)."""
    if user is None:
        return "sandbox"
    if getattr(user, "is_admin", False):
        return "institutional"
    plan = (getattr(user, "plan", None) or "sandbox").strip().lower()
    return plan if plan in PLAN_ORDER else "sandbox"


def plan_rank(plan: str) -> int:
    return PLAN_ORDER.index(plan) if plan in PLAN_ORDER else 0


def plan_label(plan: str) -> str:
    entry = PLANS.get(plan)
    return entry["name"] if entry else PLANS["sandbox"]["name"]


def _rank(user: User | None) -> int:
    return plan_rank(plan_key(user))


def can_generate_projects(user: User | None) -> bool:
    return _rank(user) >= plan_rank("student_pro") or bool(getattr(user, "is_admin", False))


def can_full_solutions(user: User | None) -> bool:
    return _rank(user) >= plan_rank("student_pro")


def can_schematic_viewer(user: User | None) -> bool:
    return _rank(user) >= plan_rank("student_pro")


def can_public_portfolio(user: User | None) -> bool:
    return _rank(user) >= plan_rank("professional")


def can_tia_bridge(user: User | None) -> bool:
    return bool(getattr(user, "is_admin", False)) or _rank(user) >= plan_rank("professional")


def fault_attempt_daily_budget(user: User | None) -> int | None:
    """None = unlimited; sandbox carries a daily graded-attempt cap."""
    if plan_key(user) == "sandbox":
        return int(get_settings().max_free_fault_attempts_per_day)
    return None


def today_fault_attempts(db: Session, user_id: int) -> int:
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(ActivityLog)
        .filter(
            ActivityLog.user_id == user_id,
            ActivityLog.action == "fault.diagnose",
            ActivityLog.created_at >= start,
        )
        .count()
    )


def enforce_fault_budget(db: Session, user: User) -> None:
    """Raise when a sandbox user hits the daily graded-attempt limit."""
    budget = fault_attempt_daily_budget(user)
    if budget is None:
        return
    if today_fault_attempts(db, user.id) >= budget:
        raise PermissionError(
            f"Free Sandbox Fault Lab limit of {budget} graded attempts/day reached. "
            "Upgrade to Student Pro or later for unlimited attempts."
        )


def trial_ends_at(user: User) -> datetime:
    return as_aware(user.created_at) + timedelta(days=int(get_settings().trial_grace_days))


def trial_days_left(user: User) -> int:
    remaining = trial_ends_at(user) - datetime.now(timezone.utc)
    return max(0, int(remaining.total_seconds() // 86400))