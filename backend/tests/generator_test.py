"""Project generation (admin) + activity audit trail. Run against a live server from backend/."""
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
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode()
            return resp.status, (json.loads(text) if text else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


results = []


def check(label, cond, extra=""):
    results.append((label, cond, extra))
    print(("PASS " if cond else "FAIL ") + label + (f"  [{extra}]" if extra else ""))


def register(label_part):
    email = f"{label_part}_{uuid.uuid4().hex[:8]}@example.com"
    st, _ = call("/auth/register", "POST", body={"email": email, "full_name": "Gen Tester", "password": "str0ngpass123"})
    st, tok = call("/auth/token", "POST", form={"username": email, "password": "str0ngpass123"})
    return email, tok["access_token"]


# --- admin user ---
admin_email, admin_token = register("admin")
db = SessionLocal()
user = db.query(User).filter(User.email == admin_email).first()
user.is_admin = True
db.commit()
db.close()

learner_email, learner_token = register("learner")

# --- generation authz ---
st, body = call("/projects/generate", "POST", body={"industry": "mining", "title": "Conveyor Interlock Logic", "difficulty": "intermediate"}, token=learner_token)
check("generate denied for non-admin", st == 403, f"status={st}")

st, body = call("/projects/generate", "POST", body={"industry": "nuclear", "title": "Bad Industry"}, token=admin_token)
check("generate rejects unknown industry", st == 422, f"status={st}")

st, new = call("/projects/generate", "POST", body={"industry": "mining", "title": "Conveyor Interlock Logic", "difficulty": "intermediate", "description": "Mining conveyor belt interlock and sequencing project."}, token=admin_token)
check("generate allowed for admin", st == 201 and new["industry"] == "mining", f"status={st} {str(new)[:140]}")
pid = new["id"]
gen_slug = new["slug"]

st, project = call(f"/projects/{pid}")
check("generated project has 17 sections", st == 200 and len(project["sections"]) == 17, f"sections={len(project.get('sections', [])) if isinstance(project, dict) else project}")

st, faults = call(f"/projects/{pid}/faults", token=learner_token)
check("generated project has published faults", st == 200 and len(faults) >= 1, f"n={len(faults) if isinstance(faults, list) else faults}")

st, manifest = call("/offline/manifest", token=admin_token)
in_manifest = any(m["project_id"] == pid for m in manifest)
check("generated project appears in offline manifest", st == 200 and in_manifest, f"manifest_n={len(manifest) if isinstance(manifest, list) else manifest}")

fp = "fp_gen_" + uuid.uuid4().hex
st, dev = call("/devices/authorize", "POST", body={"device_fingerprint": fp, "device_label": "Gen device", "platform": "test"}, token=learner_token)
check("authorize learner device for bundle", st == 200 and dev["is_authorized"], str(dev)[:100])

st, bundle = call(f"/projects/{pid}/offline-bundle?device_fingerprint={fp}", token=learner_token)
check("generated bundle downloadable", st == 200 and bundle["project"]["slug"] == gen_slug and len(bundle["faults"]) >= 1, f"status={st} faults={len(bundle.get('faults', [])) if isinstance(bundle, dict) else '?'}")

st, sec = call(f"/projects/{pid}/sections/{project['sections'][0]['key']}", token=learner_token)
check("generated section readable", st == 200 and "content" in sec, str(sec)[:100])

# --- full completion for audit-trail credential check ---
section_keys = [s["key"] for s in project["sections"]]
for i, key in enumerate(section_keys):
    st, _ = call("/progress", "POST", body={"project_id": pid, "section_key": key, "status": "completed", "score": 95 - (i % 5), "time_spent_seconds": 600}, token=learner_token)
check("all generated sections completed", st == 200, f"last={key}")

st, certs = call("/credentials/certificates", token=learner_token)
check("certificate issued after completion", st == 200 and len(certs) == 1, f"n={len(certs) if isinstance(certs, list) else certs}")

st, port = call("/credentials/portfolio", token=learner_token)
check("portfolio entry issued", st == 200 and len(port) == 1, f"n={len(port) if isinstance(port, list) else port}")

st, verified = call(f"/credentials/certificates/verify/{certs[0]['verification_token']}")
check("certificate verifies publicly", st == 200 and verified["valid"])

# fault diagnose for the generated project -> logged
st, diag = call("/fault/diagnose", "POST", body={"fault_id": faults[0]["id"], "checks": [{"check_id": "verify_instrument_power", "performed": True}], "diagnosis": "belt misalignment"}, token=learner_token)
check("diagnose works on generated fault", st == 200 and "score" in diag, f"status={st}")

# --- activity audit trail ---
st, act = call("/activity?limit=100", token=learner_token)
actions = [a["action"] for a in act]
check("activity shows section completions", "section.completed" in actions, f"count={actions.count('section.completed')}")
check("activity shows credential issue", "credential.issued" in actions)
check("activity shows fault diagnose", "fault.diagnose" in actions)
check("learner cannot see admin generate event", "project.generate" not in actions)

st, act_admin = call("/activity?limit=200", token=admin_token)
admin_actions = [a["action"] for a in act_admin]
check("admin sees cross-user generate + learner events", "project.generate" in admin_actions and "credential.issued" in admin_actions)

st, _ = call("/activity")
check("activity requires auth", st == 401, f"status={st}")

print("\n" + "=" * 60)
passed = sum(1 for _, c, _ in results if c)
print(f"{passed}/{len(results)} checks passed")
if passed != len(results):
    for label, c, extra in results:
        if not c:
            print(f"  FAIL {label}: {extra}")
    raise SystemExit(1)
print("ALL GENERATOR + ACTIVITY CHECKS PASSED")