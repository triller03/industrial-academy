"""Billing gateways / license activation against a live server.

Exercises the local test gateway, licence key redemption, and the Stripe +
Paynow webhook code paths (JSON envelopes, no live keys needed). Uses fresh
users so the demo/admin entitlement is never disturbed for other suites.

Usage: python tests/billing_test.py  (server running on 127.0.0.1:8000)
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import License, User

BASE = "http://127.0.0.1:8000/api"


def call(path, method="GET", token=None, body=None):
    data = None
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw)
        except Exception:
            payload = raw.decode(errors="replace")
        return exc.code, payload


def login(email, password):
    form = urllib.parse.urlencode({"username": email, "password": password}).encode()
    req = urllib.request.Request(BASE + "/auth/token", data=form, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())["access_token"]


def register_fresh_user():
    email = f"bill{uuid.uuid4().hex[:10]}@example.com"
    data = json.dumps({
        "email": email,
        "full_name": "Billing Tester",
        "password": "testpass1234",
        "institution": "Test",
    }).encode()
    req = urllib.request.Request(BASE + "/auth/register", data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        json.loads(resp.read())
    return email


results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))


def db_user(email) -> User | None:
    db = SessionLocal()
    try:
        return db.query(User).filter(User.email == email).first()
    finally:
        db.close()


def db_add_license(user_id, plan="student_pro", status="pending", source="web", key=None):
    db = SessionLocal()
    try:
        row = License(user_id=user_id, plan=plan, status=status, source=source,
                      license_key=key or f"TEST-{uuid.uuid4().hex[:11].upper()}")
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


fresh_email = register_fresh_user()
fresh_token = login(fresh_email, "testpass1234")
fresh_id = db_user(fresh_email).id if db_user(fresh_email) else None

demo_token = login("demo@academy.local", "demo1234")

# --- plans catalog ---------------------------------------------------------
st, _ = call("/billing/plans")
check("billing plans requires auth", st == 401, f"status={st}")
st, plans = call("/billing/plans", token=demo_token)
check("plans catalog reachable", st == 200, f"status={st}")
check("catalog advertises 4 tiers", st == 200 and sorted(plans.get("catalog", {}).keys()) ==
      ["institutional", "professional", "sandbox", "student_pro"], str(list(plans.get("catalog", {}).keys())))
check("demo resolves to professional", plans.get("current", {}).get("key") == "professional",
      str(plans.get("current", {}).get("key")))
check("demo still has trial days", isinstance(plans.get("current", {}).get("trial_days_left"), int))

# --- status gates per plan -------------------------------------------------
st, demo_status = call("/billing/status", token=demo_token)
gates = demo_status.get("gates", {})
check("professional unlocks public portfolio", gates.get("can_public_portfolio") is True, str(gates))
check("professional unlocks TIA bridge", gates.get("can_tia_bridge") is True, str(gates))

st, sand_status = call("/billing/status", token=fresh_token)
sg = sand_status.get("gates", {})
check("sandbox blocks public portfolio", sg.get("can_public_portfolio") is False, str(sg))
check("sandbox blocks TIA bridge", sg.get("can_tia_bridge") is False, str(sg))
check("sandbox blocks schematic viewer", sg.get("can_schematic_viewer") is False, str(sg))

# --- checkout validation ---------------------------------------------------
st, _ = call("/billing/checkout", "POST", token=fresh_token, body={"plan": "sandbox"})
check("checkout rejects sandbox plan", st == 422, f"status={st}")
st, bad = call("/billing/checkout", "POST", token=fresh_token, body={"plan": "nonsense"})
check("checkout rejects unknown plan", st == 422, f"status={st} detail={bad.get('detail')}")

# --- local test gateway checkout + activation ------------------------------
st, order = call("/billing/checkout", "POST", token=fresh_token, body={"plan": "student_pro"})
check("local checkout creates order", st == 200 and order.get("gateway") == "local",
      f"status={st} gateway={order.get('gateway')}")

st, act = call(f"/billing/test-checkout/{order['order_id']}", "POST", token=fresh_token)
check("test checkout activates", st == 200 and act.get("status") == "active",
      f"status={st} state={act.get('status')}")

st, licenses = call("/billing/licenses", token=fresh_token)
check("license listed for user", st == 200 and any(
    l.get("status") == "active" and l.get("plan") == "student_pro" for l in licenses), str(licenses))

st, status_after = call("/billing/status", token=fresh_token)
gates_after = status_after.get("gates", {})
check("upgraded plan unlocks schematic viewer",
      status_after.get("plan_key") == "student_pro" and gates_after.get("can_schematic_viewer"),
      f"plan={status_after.get('plan_key')}")

# --- stripe webhook happy path ---------------------------------------------
st, stripe_order = call("/billing/checkout", "POST", token=fresh_token, body={"plan": "professional"})
event = {
    "object": "event",
    "type": "checkout.session.completed",
    "data": {"object": {"metadata": {
        "order_id": str(stripe_order["order_id"]),
        "plan": "professional",
        "user_id": str(fresh_id),
    }}},
}
st, wh = call("/billing/webhook", "POST", body=event)
check("stripe webhook handled", st == 200, f"status={st} detail={wh.get('detail')}")
db = SessionLocal()
try:
    row = db.query(License).filter(License.id == stripe_order["order_id"]).first()
    check("stripe webhook activated licence", row is not None and row.status == "active",
          f"status={(row.status if row else 'missing')}")
finally:
    db.close()
st, status_after2 = call("/billing/status", token=fresh_token)
check("stripe flow raised plan to professional", status_after2.get("plan_key") == "professional",
      str(status_after2.get("plan_key")))

# --- paynow webhook envelope ------------------------------------------------
pay_email = register_fresh_user()
pay_token = login(pay_email, "testpass1234")
st, _ = call("/billing/webhook", "POST", body={
    "status": "Paid",
    "email": pay_email,
    "plan": "student_pro",
    "paynow_reference": f"PN{uuid.uuid4().hex[:10]}",
})
pay_user = db_user(pay_email)
check("paynow webhook activates", st == 200 and pay_user is not None and pay_user.plan == "student_pro",
      f"status={st} plan={(pay_user.plan if pay_user else 'none')}")
db = SessionLocal()
try:
    pn = db.query(License).filter(License.user_id == (pay_user.id if pay_user else -1),
                                  License.source == "paynow", License.status == "active").first()
    check("paynow license stored", pn is not None, "no paynow license row")
finally:
    db.close()

# --- licence key activation (web redeem) ------------------------------------
redeem_email = register_fresh_user()
redeem_token = login(redeem_email, "testpass1234")
pending = db_add_license(fresh_id, plan="student_pro", status="pending", source="web")
st, act2 = call("/billing/activate", "POST", token=redeem_token, body={"license_key": pending.license_key})
check("redeem key binds license", st == 200 and act2.get("status") == "active",
      f"status={st} detail={act2.get('detail')}")
st, redeem_status = call("/billing/status", token=redeem_token)
check("redeemed user upgraded", redeem_status.get("plan_key") == "student_pro",
      str(redeem_status.get("plan_key")))

revoked = db_add_license(fresh_id, plan="student_pro", status="revoked", source="web")
st, _ = call("/billing/activate", "POST", token=redeem_token, body={"license_key": revoked.license_key})
check("revoked key rejected", st == 403, f"status={st}")

print(f"\n== billing_test == ({len(results)} checks)")
failed = 0
for name, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not ok else ""))
    failed += 0 if ok else 1
raise SystemExit(0 if failed == 0 else 1)
