"""Learner dashboard + admin analytics checks against a live server.

Verifies /stats/learner aggregates, streak/rollup fields, the admin-only
/stats/admin cohort + per-project analytics, and 403 gating.

Usage: python tests/stats_test.py  (server must be running on 127.0.0.1:8000)
"""

import json
import urllib.error
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


def login(email, password):
    st, tok = call("/auth/token", "POST", form={"username": email, "password": password})
    if st != 200:
        raise RuntimeError(f"login failed status={st}")
    return tok["access_token"]


results = []


def check(label, cond, extra=""):
    results.append((label, cond, extra))
    print(("PASS " if cond else "FAIL ") + label + (f"  [{extra}]" if extra else ""))


email = f"stats_{uuid.uuid4().hex[:8]}@example.com"
st, reg = call("/auth/register", "POST", body={"email": email, "full_name": "Stats Tester", "password": "str0ngpass123"})
check("register stats learner", st == 201, f"status={st}")
learner_token = login(email, "str0ngpass123")

# --- fresh learner: empty stats -------------------------------------------
st, s = call("/stats/learner", token=learner_token)
check("learner stats reachable", st == 200, f"status={st}")
check("fresh learner zeroed", st == 200 and s["sections_completed"] == 0 and s["projects_started"] == 0,
      str(s["sections_completed"]))
check("streak starts at 0", s["streak_days"] == 0 and s["longest_streak"] == 0, str(s["streak_days"]))
check("daily buckets cover 14 days", len(s["daily"]) == 14, f"n={len(s['daily'])}")
check("daily buckets ascending dates", s["daily"] == sorted(s["daily"], key=lambda d: d["date"]),
      f"{s['daily'][0]['date']}..{s['daily'][-1]['date']}")
check("no projects started yet", s["projects"] == [], str(len(s["projects"])))

# --- make progress + a correct fault attempt -------------------------------
for key, secs in (("project_brief", 600), ("process_description", 600)):
    st, _ = call("/progress", "POST", token=learner_token,
                 body={"project_id": 1, "section_key": key, "status": "completed", "score": 100, "time_spent_seconds": secs})
    check(f"complete {key}", st == 200, f"status={st}")
EXPECTED = ["confirm_flow_reading", "verify_flow_signal", "check_pump_command", "check_dosing_valve", "verify_analyser_or_level_response", "check_controller_mode"]
st, diag = call("/fault/diagnose", "POST", token=learner_token,
                body={"fault_id": 1, "checks": [{"check_id": c, "performed": True} for c in EXPECTED], "diagnosis": "flowmeter failed high"})
check("diagnose correct for stats", st == 200 and diag["correct"], str(diag)[:120])

# --- learner stats after activity -----------------------------------------
st, s = call("/stats/learner", token=learner_token)
check("sections completed counted", st == 200 and s["sections_completed"] >= 2, str(s["sections_completed"]))
check("projects started counted", s["projects_started"] >= 1, str(s["projects_started"]))
check("time on site summed", s["time_spent_seconds"] >= 1200, str(s["time_spent_seconds"]))
check("fault attempt recorded", s["fault_attempts"] >= 1, str(s["fault_attempts"]))
check("correct fault counted", s["faults_correct"] >= 1, str(s["faults_correct"]))
check("fault accuracy in (0,1]", 0 < s["fault_score_avg"] <= 1, str(s["fault_score_avg"]))
check("today counts towards streak", s["streak_days"] >= 1 and s["active_days"] >= 1,
      f"streak={s['streak_days']} days={s['active_days']}")
check("daily bucket has sections", any(d["sections"] >= 2 for d in s["daily"]),
      f"sections={[d['sections'] for d in s['daily']]}")
proj = s["projects"][0]
check("project rollup present", proj["slug"] == "water-treatment-500" and proj["total_sections"] >= 17,
      f"{proj['slug']} t={proj['total_sections']}")
check("project in_progress > 0%", proj["status"] == "in_progress" and proj["percent"] > 0,
      f"{proj['status']} {proj['percent']}%")

# --- admin gating + aggregation -------------------------------------------
st, _ = call("/stats/admin", token=learner_token)
check("admin stats denied for learner", st == 403, f"status={st}")
admin_token = login("admin@academy.local", "admin1234")
st, a = call("/stats/admin", token=admin_token)
check("admin stats reachable", st == 200, f"status={st}")
check("users counted", a["users_total"] >= 3 and a["learners_total"] >= 2,
      f"{a['users_total']} users / {a['learners_total']} learners")
check("projects counted", a["projects_total"] > 0 and a["projects_published"] > 0,
      f"{a['projects_total']} proj / {a['projects_published']} pub")
check("enrollments captured", a["enrollments_total"] >= 1, str(a["enrollments_total"]))
check("sections completed total", a["sections_completed_total"] >= 2, str(a["sections_completed_total"]))
check("fault attempts total", a["fault_attempts_total"] >= 1, str(a["fault_attempts_total"]))
check("completion rate is a fraction", 0 <= a["completion_rate"] <= 1, str(a["completion_rate"]))
check("daily has 14 platform buckets", len(a["daily"]) == 14 and any(d["actions"] > 0 for d in a["daily"]),
      f"n={len(a['daily'])}")
check("by-project table non-empty", len(a["by_project"]) > 0, f"n={len(a['by_project'])}")
water = [p for p in a["by_project"] if p["slug"] == "water-treatment-500"][0]
check("water enrollments include stats learner", water["enrollments"] >= 1, str(water["enrollments"]))
check("by-industry rollup", any(i["industry"] == "water" and i["projects"] >= 1 for i in a["by_industry"]),
      str([i["industry"] for i in a["by_industry"]]))
check("recent signups listed", len(a["recent_users"]) >= 1, f"n={len(a['recent_users'])}")

print(f"\n== stats_test == ({len(results)} checks)")
failed = 0
for name, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not ok else ""))
    failed += 0 if ok else 1
raise SystemExit(0 if failed == 0 else 1)