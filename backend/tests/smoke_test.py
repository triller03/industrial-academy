"""End-to-end smoke test. Run against a live server: python tests/smoke_test.py"""
import json
import urllib.parse
import urllib.request
import uuid

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


st, h = call("/health")
check("health", st == 200 and h["status"] == "ok")

email = f"tester_{uuid.uuid4().hex[:8]}@example.com"
st, reg = call("/auth/register", "POST", body={"email": email, "full_name": "Test Tester", "password": "str0ngpass123", "institution": "MSU"})
check("register", st == 201, f"status={st} body={reg}")

st, tok = call("/auth/token", "POST", form={"username": email, "password": "str0ngpass123"})
check("login/token", st == 200 and "access_token" in tok, str(tok)[:120])
token = tok["access_token"]

st, me = call("/auth/me", token=token)
check("me", st == 200 and me["email"] == email)

st, dtok = call("/auth/token", "POST", form={"username": "demo@academy.local", "password": "demo1234"})
check("demo login (seed)", st == 200, str(dtok)[:120])

st, projects = call("/projects")
check("list projects", st == 200 and len(projects) >= 1, f"n={len(projects) if isinstance(projects, list) else projects}")
pid = projects[0]["id"]

st, project = call(f"/projects/{pid}")
check("get project (17 sections)", st == 200 and len(project["sections"]) == 17, f"sections={len(project.get('sections', [])) if isinstance(project, dict) else project}")

st, faults = call(f"/projects/{pid}/faults")
check("list faults (8)", st == 200 and len(faults) == 8, f"n={len(faults) if isinstance(faults, list) else faults}")

fid = faults[0]["id"]
st, fdetail = call(f"/projects/{pid}/faults/{fid}")
check("fault detail hides answer", st == 200 and "correct_diagnosis" not in json.dumps(fdetail) and len(fdetail["available_checks"]) >= 6)

st, m1 = call("/mentor/chat", "POST", body={"message": "How do I know where to start?", "project_id": pid, "section_key": "troubleshooting"}, token=token)
check("mentor socratic", st == 200 and m1["mode"] == "socratic", str(m1)[:140])

st, m2 = call("/mentor/chat", "POST", body={"message": "Should I just reset the breaker while the panel is live?", "project_id": pid}, token=token)
check("mentor safety override", st == 200 and m2["mode"] == "safety" and m2["safety_triggered"], str(m2)[:140])

st, m3 = call("/mentor/chat", "POST", body={"message": "I don't understand, I'm stuck and confused", "project_id": pid}, token=token)
check("mentor frustration->guided", st == 200 and m3["mode"] == "guided", str(m3)[:140])

st, m4 = call("/mentor/solution", "POST", body={"message": "full solution", "project_id": pid, "section_key": "plc_program", "history": [{"role": "user", "level": 5}]}, token=token)
check("mentor solution L5", st == 200 and m4["level"] == 5, str(m4)[:140])

fp = "fp_smoketest_" + uuid.uuid4().hex
st, dev = call("/devices/authorize", "POST", body={"device_fingerprint": fp, "device_label": "Smoke device", "platform": "test"}, token=token)
check("device authorize", st == 200 and dev["is_authorized"], str(dev)[:140])

st, prog = call("/progress", "POST", body={"project_id": pid, "section_key": "project_brief", "status": "completed", "score": 90, "time_spent_seconds": 1200}, token=token)
check("progress update", st == 200 and prog["status"] == "completed", str(prog)[:140])

st, pprog = call(f"/projects/{pid}/progress", token=token)
check("project progress (17 rows, no crash)", st == 200 and len(pprog["sections"]) == 17, f"status={st}")

expected = ["confirm_flow_reading", "verify_flow_signal", "check_pump_command", "check_dosing_valve", "verify_analyser_or_level_response", "check_controller_mode"]
st, diag = call("/fault/diagnose", "POST", body={"fault_id": fid, "checks": [{"check_id": c, "performed": True} for c in expected], "diagnosis": "flowmeter failed high"}, token=token)
check("fault diagnose correct", st == 200 and diag["correct"] and diag["score"] == 1.0, str(diag)[:160])

st, diag2 = call("/fault/diagnose", "POST", body={"fault_id": fid, "checks": [{"check_id": "check_pump_command", "performed": True}], "diagnosis": "flowmeter failed high"}, token=token)
check("fault diagnose partial", st == 200 and not diag2["correct"] and diag2["score"] < 1.0, str(diag2)[:160])

st, sy = call("/sync", "POST", body={"device_fingerprint": fp, "changes": [{"entity": "progress", "local_key": "p", "payload": {"project_id": pid, "section_key": "plc_program", "status": "completed", "score": 80, "time_spent_seconds": 3800}, "status": "completed", "score": 80}]}, token=token)
check("sync apply", st == 200 and len(sy["applied"]) == 1, str(sy)[:160])

st, sy2 = call("/sync", "POST", body={"device_fingerprint": fp, "changes": [{"entity": "progress", "local_key": "p", "payload": {"project_id": pid, "section_key": "plc_program", "status": "in_progress", "score": 10, "time_spent_seconds": 5}, "status": "in_progress", "score": 10}]}, token=token)
check("sync conflict rule", st == 200 and len(sy2["conflicts"]) == 1, str(sy2)[:200])

st, sy3 = call("/sync", "POST", body={"device_fingerprint": "fp_unknown_device", "changes": []}, token=token)
check("sync rejects unknown device", st == 403, f"status={st}")

st, dlist = call("/devices", token=token)
check("device list", st == 200 and len(dlist) >= 1)

st, rev = call("/devices/revoke", "POST", body={"device_id": dev["id"]}, token=token)
check("device revoke", st == 200)

st, certs = call("/credentials/certificates", token=token)
check("certificates list", st == 200 and certs == [])
st, port = call("/credentials/portfolio", token=token)
check("portfolio list", st == 200 and port == [])

print("\n" + "=" * 60)
passed = sum(1 for _, c, _ in results if c)
print(f"{passed}/{len(results)} checks passed")
if passed != len(results):
    for label, c, extra in results:
        if not c:
            print(f"  FAIL {label}: {extra}")
    raise SystemExit(1)
print("ALL CHECKS PASSED")
