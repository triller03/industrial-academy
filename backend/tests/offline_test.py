"""Offline layer test: bundle manifest/download + offline fault-attempt grading via sync."""
import json
import urllib.parse
import urllib.request
import uuid

BASE = "http://127.0.0.1:8000/api"


def call(path, method="GET", body=None, form=None, token=None, expect_raw=False):
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
        with urllib.request.urlopen(req, timeout=20) as r:
            txt = r.read().decode()
            return r.status, (json.loads(txt) if txt and not expect_raw else txt), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), {}


results = []


def check(label, cond, extra=""):
    results.append((label, cond, extra))
    print(("PASS " if cond else "FAIL ") + label + (f"  [{extra}]" if extra else ""))


st, tok, _ = call("/auth/token", "POST", form={"username": "demo@academy.local", "password": "demo1234"})
check("demo login", st == 200)
token = tok["access_token"]

st, projects, _ = call("/projects", token=token)
pid = next((p["id"] for p in projects if p["slug"] == "water-treatment-500"), projects[0]["id"])

fp = "fp_offline_" + uuid.uuid4().hex
call("/devices/authorize", "POST", body={"device_fingerprint": fp, "device_label": "Offline tester"}, token=token)

# manifest
st, man, _ = call("/offline/manifest", token=token)
check("manifest lists bundles", st == 200 and len(man) >= 1, f"n={len(man) if isinstance(man,list) else man}")
item = next((m for m in man if m["project_id"] == pid), man[0])
check("manifest has version/checksum/size", bool(item["version"]) and len(item["checksum"]) == 64 and item["size_bytes"] > 0,
      f"v={item['version']} size={item['size_bytes']} sections={item['section_count']} faults={item['fault_count']}")
check("manifest counts", item["section_count"] == 17 and item["fault_count"] == 8)

# download bundle (device authorized)
st, bundle, headers = call(f"/projects/{pid}/offline-bundle?device_fingerprint={fp}", token=token)
check("bundle download", st == 200 and isinstance(bundle, dict) and bundle["version"] == item["version"],
      f"status={st}")
check("bundle self-contained", len(bundle["sections"]) == 17 and len(bundle["faults"]) == 8 and "mentor_pack" in bundle)
check("bundle hides answers", "expected_checks" not in json.dumps(bundle["faults"]) and "correct_diagnosis" not in json.dumps(bundle["faults"]))
check("bundle mentor pack", len(bundle["mentor_pack"]["socratic_questions"]) > 0 and "safety_steps" in bundle["mentor_pack"])

# known_version -> 204
st, body, _ = call(f"/projects/{pid}/offline-bundle?device_fingerprint={fp}&known_version={item['version']}", token=token)
check("known version returns 204", st == 204, f"status={st}")

# unauthorized device
st, body, _ = call(f"/projects/{pid}/offline-bundle?device_fingerprint=fp_unknown_device_1234", token=token)
check("bundle rejects unknown device", st == 403, f"status={st}")

# offline fault attempt queued then synced
fid = bundle["faults"][0]["id"]
expected = [c for c in bundle["faults"][0]["available_checks"]][:6]
correct_diag = "flowmeter failed high"  # a known key for fault 1
st, sy, _ = call("/sync", "POST", body={
    "device_fingerprint": fp,
    "changes": [{
        "entity": "fault_attempt",
        "local_key": f"fault:{fid}",
        "status": "completed",
        "payload": {
            "fault_id": fid,
            "checks": [{"check_id": c, "performed": True} for c in expected],
            "diagnosis": correct_diag,
            "section_key": "fault_injection",
            "time_spent_seconds": 900,
        },
    }],
}, token=token)
applied = sy["applied"][0] if st == 200 and sy["applied"] else {}
check("offline fault attempt graded via sync", st == 200 and applied.get("entity") == "fault_attempt",
      f"status={st} applied={json.dumps(applied)[:180]}")
p = applied.get("payload", {})
check("grading returned feedback + key", p.get("correct_diagnosis") and isinstance(p.get("feedback"), list),
      f"score={p.get('score')} correct={p.get('correct')}")

# grading folded into progress
st, prog, _ = call(f"/projects/{pid}/progress", token=token)
fault_sec = next((s for s in prog["sections"] if s["section_key"] == "fault_injection"), None)
check("fault progress recorded", fault_sec is not None and fault_sec["score"] > 0,
      f"score={fault_sec['score'] if fault_sec else None}")

print("\n" + "=" * 60)
passed = sum(1 for _, c, _ in results if c)
print(f"{passed}/{len(results)} checks passed")
if passed != len(results):
    for label, c, extra in results:
        if not c:
            print(f"  FAIL {label}: {extra}")
    raise SystemExit(1)
print("ALL OFFLINE CHECKS PASSED")
