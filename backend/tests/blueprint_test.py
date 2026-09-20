"""Blueprint surface end-to-end against a live server (last suite in run_all).

Covers: Mining & Minerals track, FRS/P&ID schematic viewer gating, TIA bridge
(probe / SCL validator / tag import), project-generation gating, and the public
portfolio publish flow. Uses the demo account (professional) plus fresh sandbox
users; admin is never needed here.

Usage: python tests/blueprint_test.py  (server running on 127.0.0.1:8000)
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
from app.models import PortfolioEntry, User

BASE = "http://127.0.0.1:8000/api"
ROOT = "http://127.0.0.1:8000"

SECTION_KEYS = [
    "project_brief", "process_description", "p_and_id", "io_list", "tag_list",
    "control_philosophy", "plc_program", "hmi", "scada", "alarms", "interlocks",
    "networking", "testing", "fault_injection", "troubleshooting", "commissioning",
    "final_documentation",
]

GOOD_SCL = """FUNCTION_BLOCK FB_Crusher
VAR_INPUT
    power: REAL;
END_VAR
VAR_OUTPUT
    feeder: REAL;
END_VAR
BEGIN
    IF power > 95.0 THEN
        feeder := 0.0;
    ELSE
        feeder := 60.0;
    END_IF;
END_FUNCTION_BLOCK"""

BAD_SCL = """FUNCTION_BLOCK FB_Belt
VAR_INPUT
    run: BOOL;
END_VAR
BEGIN
    IF run THEN
        ;"""

GOOD_TAGS = "Tag,DataType,Address,Description\nFT-001,REAL,IW0.2,Influent flow\nZS-110,BOOL,I1.0,Tramp metal detector\n"
BAD_TAGS = "Tag,Address\nFT-001,IW0.2\n"


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
    email = f"bp{uuid.uuid4().hex[:10]}@example.com"
    data = json.dumps({
        "email": email,
        "full_name": "Blueprint Tester",
        "password": "testpass1234",
        "institution": "Test",
    }).encode()
    req = urllib.request.Request(BASE + "/auth/register", data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        json.loads(resp.read())
    return email


def db_user(email) -> User | None:
    db = SessionLocal()
    try:
        return db.query(User).filter(User.email == email).first()
    finally:
        db.close()


def db_add_portfolio(user_id, project_id, ref, title, summary):
    db = SessionLocal()
    try:
        entry = (
            db.query(PortfolioEntry)
            .filter(PortfolioEntry.user_id == user_id, PortfolioEntry.project_id == project_id)
            .first()
        )
        if entry:
            entry.entry_ref = ref
            entry.title = title
            entry.summary = summary
            entry.published = False
            entry.published_at = None
        else:
            entry = PortfolioEntry(
                user_id=user_id, project_id=project_id, entry_ref=ref, title=title, summary=summary,
                published=False,
            )
            db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry
    finally:
        db.close()


results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))


demo_token = login("demo@academy.local", "demo1234")
fresh_email = register_fresh_user()
fresh_token = login(fresh_email, "testpass1234")

# --- mining track -----------------------------------------------------------
st, _ = call("/curriculum/tracks")
check("tracks requires auth", st == 401, f"status={st}")
st, tracks = call("/curriculum/tracks", token=demo_token)
track_keys = [t.get("key") for t in tracks.get("tracks", [])]
check("tracks lists foundations + mining", st == 200 and "foundations" in track_keys and "mining" in track_keys,
      str(track_keys))
mining_projects = next((t.get("projects", []) for t in tracks.get("tracks", []) if t.get("key") == "mining"), [])
check("mining track advertises primary crushing",
      any(p.get("slug") == "mining-primary-crushing" for p in mining_projects), str(mining_projects))

st, mining = call("/curriculum/mining", token=demo_token)
check("mining index reachable", st == 200 and mining.get("track", {}).get("name") == "Mining & Minerals",
      f"status={st} name={mining.get('track', {}).get('name')}")

st, catalog = call("/projects", token=demo_token)
by_slug = {p["slug"]: p for p in catalog}
mining_id = by_slug.get("mining-primary-crushing", {}).get("id")
check("mining project in catalog", st == 200 and mining_id is not None,
      f"id={mining_id}")

st, body = call(f"/projects/{mining_id}", token=demo_token)
keys = [s["key"] for s in body.get("sections", [])]
check("mining project has 17 lifecycle sections", st == 200 and keys == SECTION_KEYS,
      f"n={len(keys)}")
ok_content = all(s.get("content") and len(s["content"]) > 200 for s in body.get("sections", []))
check("mining sections have real content", ok_content)

st, faults = call(f"/projects/{mining_id}/faults", token=demo_token)
check("mining project publishes >= 3 faults", st == 200 and len(faults) >= 3, f"n={len(faults)}")

# --- FRS / P&ID schematic viewer --------------------------------------------
water_id = by_slug["water-treatment-500"]["id"]
st, sch = call(f"/projects/{water_id}/schematic", token=demo_token)
check("schematic gated to student_pro+, demo gains access", st == 200 and "instruments" in sch,
      f"status={st} detail={sch.get('detail') if isinstance(sch, dict) else ''}")
check("schematic extracts instruments", st == 200 and len(sch.get("instruments", [])) >= 10,
      f"n={len(sch.get('instruments', []))}")
check("schematic extracts io map", st == 200 and len(sch.get("io", [])) >= 8,
      f"n={len(sch.get('io', []))}")
check("schematic extracts tag register", st == 200 and len(sch.get("tags", [])) >= 10,
      f"n={len(sch.get('tags', []))}")
st, _ = call(f"/projects/{water_id}/schematic", token=fresh_token)
check("sandbox blocked from schematic viewer", st == 403, f"status={st}")

# --- TIA Openness bridge ------------------------------------------------------
st, probe = call("/integrations/tia/probe", token=demo_token)
check("TIA probe accessible to professional", st == 200, f"status={st} detail={probe.get('detail')}")
check("TIA bridge degrades gracefully (no connector)", probe.get("available") is False,
      f"available={probe.get('available')}")
st, _ = call("/integrations/tia/probe", token=fresh_token)
check("sandbox blocked from TIA probe", st == 403, f"status={st}")

st, sc = call("/integrations/tia/validate-scl", "POST", token=demo_token, body={"source": GOOD_SCL})
check("valid SCL passes pre-compile", st == 200 and sc.get("ok") is True and sc.get("score", 0) > 0,
      f"status={st} ok={sc.get('ok')} score={sc.get('score')} issues={sc.get('issues')}")
st, sbad = call("/integrations/tia/validate-scl", "POST", token=demo_token, body={"source": BAD_SCL})
check("unterminated IF caught", st == 200 and sbad.get("ok") is False, f"status={st} ok={sbad.get('ok')}")
st, _ = call("/integrations/tia/validate-scl", "POST", token=fresh_token, body={"source": GOOD_SCL})
check("sandbox blocked from SCL validator", st == 403, f"status={st}")

st, imp = call("/integrations/tia/import-tags", "POST", token=demo_token,
               body={"import_name": "crushing.csv", "csv": GOOD_TAGS})
check("valid tag CSV accepted", st == 200 and imp.get("ok") is True and imp.get("rows") == 2,
      f"status={st} ok={imp.get('ok')} rows={imp.get('rows')}")
st, ibad = call("/integrations/tia/import-tags", "POST", token=demo_token,
                body={"import_name": "bad.csv", "csv": BAD_TAGS})
check("malformed tag CSV rejected", st == 200 and ibad.get("ok") is False, f"status={st} ok={ibad.get('ok')}")

req = urllib.request.Request(BASE + "/integrations/tia/template.csv", method="GET")
req.add_header("Authorization", f"Bearer {demo_token}")
with urllib.request.urlopen(req, timeout=15) as resp:
    check("tag template downloadable", resp.status == 200, f"status={resp.status}")

# --- project generation gating ----------------------------------------------
st, _ = call("/projects/generate", "POST", token=fresh_token, body={
    "industry": "mining", "title": "Sandbox Should Not Generate", "difficulty": "basic"})
check("sandbox blocked from project generation", st == 403, f"status={st}")

gen_title = f"Blueprint Mineral Plant {uuid.uuid4().hex[:6]}"
st, gen = call("/projects/generate", "POST", token=demo_token, body={
    "industry": "mining", "title": gen_title, "difficulty": "intermediate",
    "description": "Generated by the blueprint gate test."})
check("professional can generate projects", st == 201 and gen.get("slug"), f"status={st} detail={gen.get('detail')}")

# --- full-solution mentor (student pro gate) ----------------------------------
st, _ = call("/mentor/solution", "POST", token=fresh_token, body={
    "message": "Walk me through the dosing pump check sequence.",
    "project_id": water_id,
    "history": [{"role": "user", "level": 5}],
})
check("sandbox blocked from full-solution mentor", st == 403, f"status={st}")
st, sol = call("/mentor/solution", "POST", token=demo_token, body={
    "message": "Walk me through the dosing pump check sequence.",
    "project_id": water_id,
    "history": [{"role": "user", "level": 5}],
})
check("professional can request full solution", st == 200 and bool(sol.get("reply")), f"status={st}")

# --- public portfolio (professional gate) ------------------------------------
demo = db_user("demo@academy.local")
ref = f"bp-{uuid.uuid4().hex[:10]}"
entry = db_add_portfolio(demo.id, water_id, ref, "Water Treatment — Work Sample",
                         "Commissioned handover pack summary for the 500 m3/h plant.")
st, pub = call(f"/credentials/portfolio/{entry.id}/publish", "POST", token=demo_token, body={})
check("professional publishes portfolio entry", st == 200 and pub.get("published") is True,
      f"status={st} detail={pub.get('detail') if isinstance(pub, dict) else ''}")

req = urllib.request.Request(f"{ROOT}/portfolio/{ref}", method="GET")
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode(errors="replace")
        check("public portfolio page live", resp.status == 200 and "Water Treatment" in html,
              f"status={resp.status}")
except urllib.error.URLError as exc:
    check("public portfolio page live", False, str(exc))

fresh = db_user(fresh_email)
fresh_ref = f"bp-fresh-{uuid.uuid4().hex[:10]}"
fresh_entry = db_add_portfolio(fresh.id, water_id, fresh_ref, "Sandbox Entry", "Should not publish.")
st, _ = call(f"/credentials/portfolio/{fresh_entry.id}/publish", "POST", token=fresh_token, body={})
check("sandbox blocked from publishing portfolio", st == 403, f"status={st}")

st, unpub = call(f"/credentials/portfolio/{entry.id}/unpublish", "POST", token=demo_token)
check("unpublish flips entry back", st == 200 and unpub.get("published") is False, f"status={st}")
try:
    req = urllib.request.Request(f"{ROOT}/portfolio/{ref}", method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        check("unpublished entry returns 404/empty", resp.status == 404, f"status={resp.status}")
except urllib.error.HTTPError as exc:
    check("unpublished entry returns 404/empty", exc.code == 404, f"status={exc.code}")

print(f"\n== blueprint_test == ({len(results)} checks)")
failed = 0
for name, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not ok else ""))
    failed += 0 if ok else 1
raise SystemExit(0 if failed == 0 else 1)
