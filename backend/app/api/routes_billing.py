"""Billing gateways (blueprint: Stripe + Paynow, with a true local test gateway).

The platform ships with empty Stripe/Paynow keys, so a local test gateway
stands in: `/billing/test-checkout` instantly activates an order in "test"
mode — the same code path the real webhooks/front-end redirect drive. When
STRIPE_SECRET_KEY / PAYNOW_* are configured the checkout and webhook endpoints
delegate to those providers; the activation logic is shared.
"""

from __future__ import annotations

import json as _json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.activity import log_activity
from app.config import get_settings
from app.core.licensing import new_license_key, plan_expiry
from app.core.security import get_current_user
from app.database import get_db
from app.models import License, User
from app.plans import PLANS, as_aware, plan_key, plan_label, plan_rank, trial_days_left

router = APIRouter(prefix="/billing", tags=["billing"])

SOURCE_ORDER = {"pending": 0, "active": 1, "revoked": 2}


class CheckoutIn(BaseModel):
    plan: str = Field(..., description="student_pro | professional | institutional")


class ActivateIn(BaseModel):
    license_key: str = Field(min_length=8, max_length=80)


def _gateway_mode(settings) -> str:
    if settings.stripe_secret_key and settings.stripe_price_map:
        return "stripe"
    if settings.paynow_integration_id and settings.paynow_api_key:
        return "paynow"
    return "local"


def _effective_plan(db: Session, user: User) -> str:
    """Highest ranked active license wins over the stored plan (admin stays institutional)."""
    if user.is_admin:
        return "institutional"
    active = (
        db.query(License)
        .filter(License.user_id == user.id, License.status == "active")
        .all()
    )
    best = plan_key(user)
    for lic in active:
        if plan_rank(lic.plan) > plan_rank(best) and (
            lic.expires_at is None or as_aware(lic.expires_at) > datetime.now(timezone.utc)
        ):
            best = lic.plan
    return best


def _apply_license(db: Session, user: User, license_row: License, hwid: str | None = None) -> None:
    """Activate a licence row and lift the owner's plan."""
    license_row.status = "active"
    license_row.activated_at = datetime.now(timezone.utc)
    if hwid:
        license_row.hwid = hwid
    if plan_rank(license_row.plan) > plan_rank(user.plan or "sandbox"):
        user.plan = license_row.plan
    db.add(license_row)
    db.add(user)


@router.get("/plans")
def list_plans(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    """Pricing catalog with the caller's current entitlement."""
    effective = _effective_plan(db, current)
    return {
        "catalog": PLANS,
        "current": {
            "key": effective,
            "label": plan_label(effective),
            "trial_days_left": trial_days_left(current),
        },
        "gateway": _gateway_mode(get_settings()),
    }


@router.get("/licenses")
def my_licenses(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    rows = db.query(License).filter(License.user_id == current.id).order_by(License.id.desc()).all()
    return [
        {
            "id": row.id,
            "license_key": row.license_key,
            "plan": row.plan,
            "status": row.status,
            "source": row.source,
            "price_usd": row.price_usd,
            "hwid": row.hwid,
            "issued_at": row.issued_at,
            "activated_at": row.activated_at,
            "expires_at": row.expires_at,
        }
        for row in rows
    ]


@router.get("/status")
def billing_status(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    effective = _effective_plan(db, current)
    active = [row for row in db.query(License).filter(License.user_id == current.id).all() if row.status == "active"]
    next_expiry = min([row.expires_at for row in active if row.expires_at], default=None)
    return {
        "plan_key": effective,
        "plan_label": plan_label(effective),
        "plan": getattr(current, "plan", "sandbox"),
        "trial_days_left": trial_days_left(current),
        "next_renewal": next_expiry,
        "gates": {
            "can_generate_projects": plan_rank(effective) >= plan_rank("student_pro"),
            "can_full_solutions": plan_rank(effective) >= plan_rank("student_pro"),
            "can_schematic_viewer": plan_rank(effective) >= plan_rank("student_pro"),
            "can_public_portfolio": plan_rank(effective) >= plan_rank("professional"),
            "can_tia_bridge": current.is_admin or plan_rank(effective) >= plan_rank("professional"),
        },
    }


@router.post("/checkout")
def checkout(
    body: CheckoutIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Create an order. Returns a provider-aware redirect surface for the webview."""
    if body.plan not in PLANS or body.plan == "sandbox":
        raise HTTPException(status_code=422, detail="Pick student_pro, professional or institutional.")
    settings = get_settings()
    source = _gateway_mode(settings)
    row = License(
        user_id=current.id,
        license_key=new_license_key(),
        plan=body.plan,
        status="pending",
        source=source,
        price_usd=PLANS[body.plan]["price_usd"],
        expires_at=plan_expiry(),
    )
    db.add(row)
    log_activity(db, current.id, "billing.checkout", entity=f"license:{row.license_key}",
                 detail={"plan": body.plan, "gateway": source})
    db.commit()
    db.refresh(row)

    if source == "local":
        return {
            "order_id": row.id,
            "license_key": row.license_key,
            "plan": body.plan,
            "price_usd": PLANS[body.plan]["price_usd"],
            "gateway": "local",
            "confirm_url": f"/api/billing/test-checkout/{row.id}",
        }
    if source == "stripe":
        try:
            import stripe  # type: ignore

            price = _json.loads(settings.stripe_price_map or "{}").get(body.plan)
            session = stripe.checkout.Session.create(
                api_key=settings.stripe_secret_key,
                mode="payment",
                customer_email=current.email,
                line_items=[{"price": price, "quantity": 1}],
                metadata={"order_id": str(row.id), "plan": body.plan, "user_id": str(current.id)},
            )
            return {"order_id": row.id, "gateway": "stripe", "checkout_url": session.url}
        except Exception as exc:  # pragma: no cover - depends on live keys
            raise HTTPException(status_code=502, detail=f"Stripe checkout failed: {exc}")
    # paynow
    return {
        "order_id": row.id,
        "gateway": "paynow",
        "poll": settings.paynow_result_url or "",
        "license_key": row.license_key,
        "confirm_url": f"/api/billing/paynow/verify/{row.id}",
    }


@router.post("/test-checkout/{order_id}")
def test_checkout(
    order_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Local test gateway: instantly activates the order for the demo/eval flow."""
    row = (
        db.query(License)
        .filter(License.id == order_id, License.user_id == current.id)
        .first()
    )
    if not row or row.status != "pending":
        raise HTTPException(status_code=404, detail="No pending order for this user.")
    _apply_license(db, current, row)
    log_activity(db, current.id, "billing.paid_test", entity=f"license:{row.license_key}",
                 detail={"plan": row.plan, "gateway": "test"})
    db.commit()
    return {
        "order_id": row.id,
        "license_key": row.license_key,
        "plan": row.plan,
        "status": row.status,
        "expires_at": row.expires_at,
        "plan_now": row.plan,
    }


@router.post("/activate")
def activate(
    body: ActivateIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Redeem a purchased licence key (web/paynow + email flow)."""
    row = db.query(License).filter(License.license_key == body.license_key.strip()).first()
    if not row:
        raise HTTPException(status_code=404, detail="License key not recognised.")
    if row.status == "revoked":
        raise HTTPException(status_code=403, detail="This license key has been revoked.")
    if row.status == "active" and row.user_id != current.id:
        raise HTTPException(status_code=409, detail="This license key is already activated on another account.")
    row.user_id = current.id
    _apply_license(db, current, row)
    log_activity(db, current.id, "billing.activate", entity=f"license:{row.license_key}",
                 detail={"plan": row.plan, "source": row.source})
    db.commit()
    return {
        "license_key": row.license_key,
        "plan": row.plan,
        "status": row.status,
        "expires_at": row.expires_at,
        "plan_now": current.plan or plan_key(current),
    }


def _stripe_event(request: Request) -> dict | None:
    settings = get_settings()
    payload = request.state.body or b""
    try:
        event = _json.loads(payload)
    except Exception:
        return None
    return event


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe + Paynow webhook. Local test gateway never calls this."""
    settings = get_settings()
    raw = await request.body()
    request.state.body = raw
    event = _stripe_event(request)
    if not event:
        raise HTTPException(status_code=400, detail="Unreadable event body.")

    if event.get("object") == "event":  # Stripe envelope
        if event.get("type") == "checkout.session.completed":
            meta = (event.get("data") or {}).get("object", {}).get("metadata", {})
            order_id = meta.get("order_id")
            plan = meta.get("plan")
            user_id = meta.get("user_id")
            if not order_id or not plan or not user_id:
                raise HTTPException(status_code=400, detail="Missing metadata on session")
            row = db.query(License).filter(License.id == int(order_id)).first()
            if row and row.status == "pending":
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user:
                    _apply_license(db, user, row, hwid=None)
                    log_activity(db, user.id, "billing.stripe_paid", entity=f"license:{row.license_key}",
                                 detail={"plan": row.plan})
                db.commit()
            return {"ok": True}

    if event.get("status") == "Paid":  # Paynow envelope
        paynow_reference = event.get("reference") or event.get("paynow_reference")
        plan = event.get("plan")
        email = event.get("email")
        user = db.query(User).filter(User.email == email).first() if email else None
        if user and plan:
            row = License(
                user_id=user.id,
                license_key=new_license_key(),
                plan=plan,
                status="pending",
                source="paynow",
                price_usd=PLANS[plan].get("price_usd") if plan in PLANS else None,
                expires_at=plan_expiry(),
            )
            db.add(row)
            db.flush()
            _apply_license(db, user, row)
            log_activity(db, user.id, "billing.paynow_paid", entity=f"license:{row.license_key}",
                         detail={"plan": row.plan, "paynow_reference": paynow_reference})
            db.commit()
            return {"ok": True}
        raise HTTPException(status_code=400, detail="Paynow event missing user/plan")

    raise HTTPException(status_code=400, detail="Unhandled event")