"""Offline admin + auth-path tests. Run against a live server from backend/."""
import json
import sys
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import User

BASE = "http://127.0.0.1:8000/api"


def call(path, method="GET", body=None, form=None, token=None):
    headers = {}
    data = None
    if token:
        headers["Authorization"] = "Bearer " + token
    if form is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        data = urllib.parse.urlencode(form).encode()
    elif body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode()
            return resp.status, (json.loads(text) if text else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


results = []


def check(label, cond, extra=""):
    results.append((label, cond, extra))
    print(("PASS " if cond else "FAIL ") + label + (f"  [{extra}]" if extra else ""))


email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
st, reg = call("/auth/register", "POST", body={"email": email, "full_name": "Admin Test", "password": "str0ngpass123"})
check("register test user", st == 201, f"status={st}")

st, tok = call("/auth/token", "POST", form={"username": email, "password": "str0ngpass123"})
token = tok["access_token"]
check("login", st == 200)

st, _ = call("/offline/manifest")
check("manifest requires auth", st == 401, f"status={st}")

st, body = call("/offline/rebuild", "POST", token=token)
check("rebuild denied for non-admin", st == 403, f"status={st} body={body}")

db = SessionLocal()
user = db.query(User).filter(User.email == email).first()
user.is_admin = True
db.commit()
db.close()

st, body = call("/offline/rebuild", "POST", token=token)
check("rebuild allowed for admin", st == 200 and isinstance(body, dict), f"status={st}")
check("rebuild idempotent (no content change)", body.get("written") == 0, f"written={body.get('written')}")

st, manifest = call("/offline/manifest", token=token)
check("manifest lists bundles for auth user", st == 200 and len(manifest) >= 1, f"n={len(manifest) if isinstance(manifest, list) else manifest}")
proj = manifest[0]

st, _ = call(f"/offline/rebuild", "POST", token=token)
st2, manifest2 = call("/offline/manifest", token=token)
check("manifest version stable after rebuild", st2 == 200 and manifest2[0]["version"] == proj["version"], f"{proj['version']}")

fp = "fp_admin_" + uuid.uuid4().hex
st, dev = call("/devices/authorize", "POST", body={"device_fingerprint": fp, "device_label": "Admin device", "platform": "test"}, token=token)
check("authorize device for bundle test", st == 200 and dev["is_authorized"], str(dev)[:100])

st, body = call(f"/projects/{proj['project_id']}/offline-bundle?device_fingerprint={fp}", token=token)
check("bundle download matches manifest version", st == 200 and body["version"] == proj["version"], f"v={body.get('version') if isinstance(body, dict) else None}")

st, body = call("/projects/999999/offline-bundle?device_fingerprint=" + fp, token=token)
check("bundle download 404 for unknown project", st == 404, f"status={st}")

print("\n" + "=" * 60)
passed = sum(1 for _, c, _ in results if c)
print(f"{passed}/{len(results)} checks passed")
if passed != len(results):
    for label, c, extra in results:
        if not c:
            print(f"  FAIL {label}: {extra}")
    raise SystemExit(1)
print("ALL ADMIN OFFLINE CHECKS PASSED")