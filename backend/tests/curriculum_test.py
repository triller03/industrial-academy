"""Curriculum content checks against a live server.

Verifies the four authored foundations projects are present with the exact 17-section
lifecycle, their fault scenarios are published, bundles are downloadable, the
curriculum index is correct, and the admin install action is idempotent + guarded.

Usage: python tests/curriculum_test.py  (server must be running on 127.0.0.1:8000)
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000/api"

EXPECTED_SLUGS = [
    "motor-starter-basics",
    "instrument-loop-checkout",
    "conveyor-sorter-cell",
    "chlorine-dosing-skid",
]

SECTION_KEYS = [
    "project_brief",
    "process_description",
    "p_and_id",
    "io_list",
    "tag_list",
    "control_philosophy",
    "plc_program",
    "hmi",
    "scada",
    "alarms",
    "interlocks",
    "networking",
    "testing",
    "fault_injection",
    "troubleshooting",
    "commissioning",
    "final_documentation",
]


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
        payload = json.loads(resp.read())
    return payload["access_token"]


results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))


demo_token = login("demo@academy.local", "demo1234")
admin_token = login("admin@academy.local", "admin1234")

# --- index auth ------------------------------------------------------------
st, _ = call("/curriculum")
check("curriculum index requires auth", st == 401, f"status={st}")

# --- projects present ------------------------------------------------------
st, projects = call("/projects", token=demo_token)
by_slug = {p["slug"]: p for p in projects}
miss = [s for s in EXPECTED_SLUGS if s not in by_slug]
check("all 4 curriculum projects in catalog", st == 200 and not miss, f"missing={miss}")

# --- curriculum index ------------------------------------------------------
st, index = call("/curriculum", token=demo_token)
check("curriculum index reachable", st == 200, f"status={st}")
check("track name correct", index.get("track", {}).get("name") == "Automation Technician Foundations",
      str(index.get("track", {}).get("name")))
check("track lists 4 projects in order",
      [p["slug"] for p in index.get("projects", [])] == EXPECTED_SLUGS,
      str([p["slug"] for p in index.get("projects", [])]))

# --- per-project content ---------------------------------------------------
proc_detail = {}
for slug in EXPECTED_SLUGS:
    pid = by_slug[slug]["id"]
    st, body = call(f"/projects/{pid}", token=demo_token)
    keys = [s["key"] for s in body.get("sections", [])]
    ok_content = all(s.get("content") and len(s["content"]) > 200 for s in body.get("sections", []))
    check(f"{slug} has 17 lifecycle sections in order", st == 200 and keys == SECTION_KEYS,
          f"n={len(keys)}")
    check(f"{slug} sections have real content", ok_content)
    proc_detail[slug] = body

    st, faults = call(f"/projects/{pid}/faults", token=demo_token)
    check(f"{slug} publishes >= 3 faults", st == 200 and len(faults) >= 3, f"n={len(faults)}")
    for f in faults[:2]:
        st, fd = call(f"/projects/{pid}/faults/{f['id']}", token=demo_token)
        check(f"{slug} fault details expose palette", st == 200 and len(fd.get("available_checks", [])) >= 5,
              f"checks={len(fd.get('available_checks', []))}")

# --- offline bundles carried -----------------------------------------------
st, manifest = call("/offline/manifest", token=admin_token)
manifest_ids = {m["project_id"] for m in manifest}
for slug in EXPECTED_SLUGS:
    pid = by_slug[slug]["id"]
    check(f"{slug} has an offline bundle", pid in manifest_ids)

# --- one fault diagnosis end-to-end (motor project) --------------------------
F1_CHECKS = [
    "check_start_command",
    "check_estop_chain",
    "check_overload_relay",
    "check_cooling_fan_switch",
    "check_door_interlock",
    "check_plc_output_state",
    "check_auto_mode_selector",
]
st, body = call(f"/projects/{by_slug['motor-starter-basics']['id']}/faults", token=demo_token)
fault = body[0]
st, detail = call(f"/projects/{by_slug['motor-starter-basics']['id']}/faults/{fault['id']}", token=demo_token)
check("motor F1 palette contains the authored checks", st == 200 and set(F1_CHECKS) <= set(detail["available_checks"]),
      f"n={len(detail.get('available_checks', []))}")
performed = [{"check_id": c, "performed": True} for c in F1_CHECKS]
st, graded = call("/fault/diagnose", "POST", token=demo_token, body={
    "fault_id": fault["id"],
    "checks": performed,
    "diagnosis": "motor cubicle door interlock open blocking the run command via the healthy header",
})
check("diagnosis grades correct (motor F1)", st == 200 and graded.get("correct") is True,
      f"status={st} correct={graded.get('correct')}")

# --- admin install: guarded + idempotent ------------------------------------
st, _ = call("/curriculum/install", "POST", token=demo_token)
check("install denied for non-admin", st == 403, f"status={st}")
st, _ = call("/curriculum/install", "POST")
check("install denied unauthenticated", st == 401, f"status={st}")
st, res = call("/curriculum/install", "POST", token=admin_token)
check("install runs for admin", st == 200, f"status={st} detail={res.get('detail')}")
check("install idempotent (nothing new)", res.get("created") == [], str(res.get("created")))

print(f"\n== curriculum_test == ({len(results)} checks)")
failed = 0
for name, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not ok else ""))
    failed += 0 if ok else 1
raise SystemExit(0 if failed == 0 else 1)