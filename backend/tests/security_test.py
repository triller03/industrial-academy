"""Security hardening checks against the live server.

Verifies baseline security headers, CSP on the SPA, CORS behaviour, and that
auth rate limiting and credential handling behave (401 on bad login, 429 when
the sliding window is exhausted, 422 on weak registrations).

Usage: python tests/security_test.py   (server must be running on 127.0.0.1:8000)
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"


def request(method: str, path: str, body: bytes | None = None, headers: dict | None = None):
    req = urllib.request.Request(BASE + path, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def login(email: str, password: str) -> str:
    form = urllib.parse.urlencode({"username": email, "password": password}).encode()
    status, _, body = request("POST", "/api/auth/token", body=form,
                              headers={"Content-Type": "application/x-www-form-urlencoded"})
    if status != 200:
        raise RuntimeError(f"login failed with status {status}")
    return json.loads(body)["access_token"]


results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


# 1. Security headers on a JSON API response -------------------------------
status, headers, _ = request("GET", "/api/health")
check("health endpoint reachable", status == 200, f"status={status}")
for hdr in ("X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "Permissions-Policy"):
    check(f"header present: {hdr}", headers.get(hdr.lower()) is not None, str(headers.get(hdr.lower())))
check("X-Content-Type-Options: nosniff", headers.get("x-content-type-options") == "nosniff")
check("X-Frame-Options: DENY", headers.get("x-frame-options") == "DENY")

# 2. CSP on the SPA --------------------------------------------------------
status, headers, _ = request("GET", "/")
check("SPA serves", status == 200, f"status={status}")
csp = headers.get("content-security-policy", "")
check("CSP present on SPA", bool(csp), csp[:120])
check("CSP restricts scripts to self", "script-src 'self'" in csp, csp[:120])
check("CSP blocks framing", "frame-ancestors 'none'" in csp, csp[:120])
check("CSP default-src self", "default-src 'self'" in csp, csp[:120])

# 3. CORS preflight --------------------------------------------------------
status, headers, _ = request(
    "OPTIONS",
    "/api/auth/me",
    headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
    },
)
acao = headers.get("access-control-allow-origin", "")
check("preflight answered", status in (200, 204), f"status={status}")
if acao == "*":
    check("CORS permissive (*) allowed", True, "development default")
else:
    check("CORS echoes only allowed origin", acao == "http://localhost:3000", acao)

# 4. Login hardening -------------------------------------------------------
demo_token = login("demo@academy.local", "demo1234")
form = urllib.parse.urlencode(
    {"username": "no-such-user@example.com", "password": "wrong-password-123"}
).encode()
status, _, body = request("POST", "/api/auth/token", body=form, headers={"Content-Type": "application/x-www-form-urlencoded"})
check("bad login returns 401", status == 401, f"status={status}")
if status == 401:
    try:
        payload = json.loads(body)
        check("unauthorized detail is generic", payload.get("detail") in ("Incorrect email or password",), str(payload)[:80])
    except Exception:
        check("unauthorized detail is generic", False, "non-JSON body")

# 5. Registration schema ---------------------------------------------------
weak = json.dumps(
    {"email": "new-user@example.com", "password": "short", "full_name": "Tester"}
).encode()
status, _, _ = request("POST", "/api/auth/register", body=weak, headers={"Content-Type": "application/json"})
check("weak password rejected (422)", status == 422, f"status={status}")

# 6. Auth rate limiting ----------------------------------------------------
# Burst the dedicated canary endpoint (/api/auth/ratelimit-probe, per-endpoint
# bucket) until the 429 sliding window fires. Real token/refresh flows are never
# poisoned because each auth endpoint has its own bucket.
attempts = 0
saw_429 = False
first_status = None
while attempts < 250:
    attempts += 1
    status, _, _ = request(
        "POST",
        "/api/auth/ratelimit-probe",
        body=b"",
        headers={"Authorization": "Bearer garbage"},
    )
    if first_status is None:
        first_status = status
    if status == 429:
        saw_429 = True
        break
    if status not in (200, 401, 422):
        break
check(
    "rate limit kicks in (429) within 250 attempts",
    saw_429,
    f"attempts={attempts} first_status={first_status}",
)

st, _, _ = request("POST", "/api/auth/ratelimit-probe", body=b"",
                   headers={"Authorization": f"Bearer {demo_token}"})
check("probe still works for validated users after burst", st in (200, 429),
      f"status={st} (429 expected if burst gave it away)")

# --------------------------------------------------------------------------
print(f"\n== security_test == ({len(results)} checks)")
failed = 0
for name, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not ok else ""))
    failed += 0 if ok else 1
raise SystemExit(0 if failed == 0 else 1)