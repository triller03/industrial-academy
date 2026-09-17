"""Refresh-token rotation test."""
import json
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000/api"


def call(path, method="GET", body=None, form=None, token=None):
    h = {}; d = None
    if token: h["Authorization"] = "Bearer " + token
    if form is not None:
        h["Content-Type"] = "application/x-www-form-urlencoded"; d = urllib.parse.urlencode(form).encode()
    elif body is not None:
        h["Content-Type"] = "application/json"; d = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=d, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            t = r.read().decode(); return r.status, (json.loads(t) if t else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


ok = True
st, tok = call("/auth/token", "POST", form={"username": "demo@academy.local", "password": "demo1234"})
print("login:", st, "has refresh:", bool(tok.get("refresh_token")) if st == 200 else tok)
ok &= st == 200 and bool(tok.get("refresh_token"))

st, new = call("/auth/refresh", "POST", body={"refresh_token": tok["refresh_token"]})
print("refresh:", st, "rotated:", bool(new.get("refresh_token")) if st == 200 else new)
ok &= st == 200 and new.get("access_token") and new.get("refresh_token") != tok["refresh_token"]

st, me = call("/auth/me", token=new["access_token"])
print("new access token works:", st, me.get("email") if st == 200 else me)
ok &= st == 200

st, reused = call("/auth/refresh", "POST", body={"refresh_token": tok["refresh_token"]})
print("old refresh rejected (reuse):", st)
ok &= st == 401

st, bad = call("/auth/refresh", "POST", body={"refresh_token": "not-a-real-token"})
print("garbage refresh rejected:", st)
ok &= st == 401

print("REFRESH FLOW:", "PASS" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
