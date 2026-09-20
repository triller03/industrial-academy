"""HWID licensing / offline tokens against a live server.

Verifies the signed offline licence flow: status returns a JWT bound to the
user's authorised hardware ids, register-hwid enforces the device limit, and
the verify endpoint validates (and rejects tampered/unknown) tokens.

Usage: python tests/licensing_test.py  (server running on 127.0.0.1:8000)
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

from jose import jwt

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
    email = f"lic{uuid.uuid4().hex[:10]}@example.com"
    data = json.dumps({
        "email": email,
        "full_name": "Licensing Tester",
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


token = login("demo@academy.local", "demo1234")

st, _ = call("/licensing/status")
check("licensing status requires auth", st == 401, f"status={st}")

st, status = call("/licensing/status", token=token)
check("licensing status reachable", st == 200, f"status={st}")
offline = status.get("offline_token", "")
check("offline token issued", st == 200 and len(offline) > 40, f"len={len(offline)}")

# decode without the secret — payload contract
payload = jwt.decode(offline, "", options={"verify_signature": False})
check("token carries licence type", payload.get("typ") == "license", str(payload.get("typ")))
check("token issuer marker", payload.get("iss") == "asapa-license", str(payload.get("iss")))
check("token binds plan", payload.get("plan") == "professional", str(payload.get("plan")))
check("token binds hwids list", isinstance(payload.get("hwids"), list), str(payload.get("hwids")))
check("token has expiry", payload.get("exp") is not None, "")

st, verified = call("/licensing/verify", "POST", body={"offline_token": offline})
check("verify accepts genuine token", st == 200 and verified.get("valid") is True,
      f"status={st} detail={verified.get('detail')}")

tampered = offline[:20] + ("A" if offline[20] != "A" else "B") + offline[21:]
st, _ = call("/licensing/verify", "POST", body={"offline_token": tampered})
check("verify rejects tampered token", st == 401, f"status={st}")

st, _ = call("/licensing/verify", "POST", body={"offline_token": "complete-nonsense"})
check("verify rejects garbage token", st == 401, f"status={st}")

# --- fresh user HWID binding ------------------------------------------------
email = register_fresh_user()
t2 = login(email, "testpass1234")

hwids = [f"HW-{uuid.uuid4().hex[:20]}" for _ in range(4)]
for i, hwid in enumerate(hwids[:3]):
    st, r = call("/licensing/register-hwid", "POST", token=t2, body={"hwid": hwid, "label": f"unit {i + 1}", "platform": "test"})
    check(f"register hwid {i + 1}/3 bound", st == 200 and hwid in r.get("bound_hwids", []),
          f"status={st} bound={len(r.get('bound_hwids', []))}")
    if i == 2:
        check("device limit advertised", r.get("device_limit") == 3, str(r.get("device_limit")))
        tok = r.get("offline_token", "")
        p = jwt.decode(tok, "", options={"verify_signature": False})
        check("token caps hwids at device limit", len(p.get("hwids", [])) == 3, str(p.get("hwids")))

st, _ = call("/licensing/register-hwid", "POST", token=t2, body={"hwid": hwids[3]})
check("4th hwid rejected", st == 403, f"status={st}")

# demo is professional -> plan already, ensure token reflects it and is valid
st, final = call("/licensing/verify", "POST", body={"offline_token": tok})
check("bound-user token still valid", st == 200 and len(final.get("bound_hwids", [])) == 3,
      str(final.get("bound_hwids")))

print(f"\n== licensing_test == ({len(results)} checks)")
failed = 0
for name, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not ok else ""))
    failed += 0 if ok else 1
raise SystemExit(0 if failed == 0 else 1)
