"""Engineering Desk / orchestration engine end-to-end.

Covers: auth guard, toolchain status (TIA / WinCC / Factory I/O), the seven-stage
project lifecycle state machine (advance / regress / clamping), plan gates on
gated stages, and the admin-only tool launch endpoint (simulated on this host).
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = "http://127.0.0.1:8000/api"

STAGE_KEYS = ["kickoff", "engineering", "schematic", "plc", "hmi", "simulation", "handover"]


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
        with urllib.request.urlopen(req, timeout=30) as resp:
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
    email = f"orch{uuid.uuid4().hex[:10]}@example.com"
    data = json.dumps({
        "email": email, "full_name": "Orchestration Tester",
        "password": "testpass1234", "institution": "Test",
    }).encode()
    req = urllib.request.Request(BASE + "/auth/register", data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        json.loads(resp.read())
    return email


results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))


demo_token = login("demo@academy.local", "demo1234")
admin_token = login("admin@academy.local", "admin1234")
fresh_email = register_fresh_user()
fresh_token = login(fresh_email, "testpass1234")

# --- auth guard ---------------------------------------------------------------
st, _ = call("/orchestrator/status")
check("orchestrator status requires auth", st == 401, f"status={st}")

# --- toolchain status ----------------------------------------------------------
st, sts = call("/orchestrator/status", token=demo_token)
check("status reachable to authenticated user", st == 200, f"status={st}")
check("status is enabled", sts.get("enabled") is True, f"enabled={sts.get('enabled')}")
pipeline = sts.get("pipeline", [])
check("pipeline has all 7 stages", [s["key"] for s in pipeline] == STAGE_KEYS,
      f"keys={[s.get('key') for s in pipeline]}")
tools = sts.get("tools", {})
check("toolchain reports TIA / WinCC / Factory I/O",
      all(k in tools for k in ("tia", "wincc", "factoryio")), f"tools={list(tools)}")
check("mode is simulate on this host", sts.get("mode") == "simulate",
      f"mode={sts.get('mode')}")
check("factoryio degrades to simulated when not installed",
      tools.get("factoryio", {}).get("state") == "simulated",
      f"state={tools.get('factoryio', {}).get('state')}")

# --- project lifecycle state machine ------------------------------------------
st, catalog = call("/projects", token=demo_token)
pid = [p["id"] for p in catalog][0]

st, wf = call(f"/orchestrator/projects/{pid}/workflow", token=demo_token)
check("workflow starts at kickoff", st == 200 and wf.get("stage_key") == "kickoff" and wf.get("stage_index") == 0,
      f"status={st} key={wf.get('stage_key')} idx={wf.get('stage_index')}")
check("workflow carries pipeline definition", st == 200 and len(wf.get("pipeline", [])) == 7,
      f"n={len(wf.get('pipeline', []))}")

# advance chronologically through a few stages
advances = []
for expected in ("engineering", "schematic", "plc", "hmi", "simulation", "handover"):
    st, res = call(f"/orchestrator/projects/{pid}/advance", "POST", token=demo_token, body={"step": 1})
    advances.append((st, res.get("stage_key")))
ok_advance = all(s == 200 and k == e for (s, k), e in zip(advances, ("engineering", "schematic", "plc", "hmi", "simulation", "handover")))
check("advance walks every stage in order", ok_advance, f"keys={[k for _, k in advances]}")

st, res = call(f"/orchestrator/projects/{pid}/advance", "POST", token=demo_token, body={"step": 3})
check("advance clamps at handover", st == 200 and res.get("completed") is True and res.get("stage_index") == 6,
      f"status={st} idx={res.get('stage_index')} completed={res.get('completed')}")

st, res = call(f"/orchestrator/projects/{pid}/regress", "POST", token=demo_token)
check("regress steps back from handover", st == 200 and res.get("stage_key") == "simulation",
      f"status={st} key={res.get('stage_key')}")

# reset to zero then clamp at bottom
for _ in range(10):
    call(f"/orchestrator/projects/{pid}/regress", "POST", token=demo_token)
st, res = call(f"/orchestrator/projects/{pid}/workflow", token=demo_token)
check("regress clamps at kickoff", st == 200 and res.get("stage_index") == 0, f"idx={res.get('stage_index')}")

st, _ = call("/orchestrator/projects/999999/workflow", token=demo_token)
check("unknown project returns 404", st == 404, f"status={st}")

# --- plan gates on gated stages ------------------------------------------------
st, _ = call(f"/orchestrator/projects/{pid}/regress", "POST", token=demo_token)  # ensure at 0
st, res = call(f"/orchestrator/projects/{pid}/advance", "POST", token=fresh_token, body={"step": 1})
check("sandbox blocked entering gated engineering stage", st == 403, f"status={st} detail={res.get('detail')}")

# --- tool launch (admin only, simulated on this host) --------------------------
st, _ = call("/orchestrator/tools/factoryio/launch", "POST", token=demo_token, body={"actions": ["open:factoryio"]})
check("non-admin blocked from tool launch", st == 403, f"status={st}")
st, res = call("/orchestrator/tools/factoryio/launch", "POST", token=admin_token, body={"actions": ["open:factoryio"]})
check("admin launches simulated Factory I/O", st == 200 and res.get("ok") is True and res.get("mode") == "simulate",
      f"status={st} ok={res.get('ok')} mode={res.get('mode')} detail={res.get('detail')}")
st, _ = call("/orchestrator/tools/notatool/launch", "POST", token=admin_token, body={"actions": []})
check("unknown tool rejected", st == 422, f"status={st}")

print(f"\n== orchestrator_test == ({len(results)} checks)")
failed = 0
for name, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not ok else ""))
    failed += 0 if ok else 1
raise SystemExit(0 if failed == 0 else 1)