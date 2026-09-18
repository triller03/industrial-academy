"""Integration-layer checks: FACTORY I/O (Modbus TCP) bridge status, live
simulated-plant snapshot, a real Modbus client round-trip, admin controls and
the audit trail. Requires the API server on 127.0.0.1:8000."""

import json
import time
import urllib.parse
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"


def _post(path, body=None, token=None, form=False):
    headers = {}
    if form:
        data = urllib.parse.urlencode(body or {}).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    else:
        data = json.dumps(body or {}).encode() if body is not None else None
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _get(path, token=None):
    headers = {"Authorization": "Bearer " + token} if token else {}
    req = urllib.request.Request(BASE + path, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def expect(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""))
    if not condition:
        raise AssertionError(name)


def main():
    token = _post("/api/auth/token", {"username": "admin@academy.local", "password": "admin1234"}, form=True)["access_token"]

    status = _get("/api/integrations", token=token)
    expect("all links reported", set(status) >= {"state", "events", "modbus", "s7", "opcua"})
    expect("modbus running", status["modbus"]["state"] == "running", status["modbus"].get("detail", ""))

    time.sleep(2)
    status = _get("/api/integrations", token=token)
    snap = status["modbus"].get("snapshot", {})
    sensors = snap.get("sensors", {})
    measurements = snap.get("measurements", {})
    expect("simulated plant writes sensors", "running_lamp" in sensors and "tank_low" in sensors)
    expect("simulated plant writes measurements", "level" in measurements and "speed" in measurements)
    expect("command channel captured", "conveyor_run" in snap.get("actuators", {}))

    from pymodbus.client import ModbusTcpClient
    client = ModbusTcpClient("127.0.0.1", port=502, timeout=5)
    expect("modbus client connects", client.connect())
    got = client.write_coil(0, True)
    client.write_register(0, 500)  # speed setpoint = 5.00
    rr = client.read_coils(0, count=8)
    hr = client.read_holding_registers(0, count=5)
    client.close()
    expect("client can hold coil writes", bool(got) and rr.isError() is False and hr.isError() is False)
    expect("coil echoed true", rr.bits[0] is True)
    expect("holding register echoed", hr.registers[0] == 500)

    status = _get("/api/integrations", token=token)
    snap = status["modbus"].get("snapshot", {})
    expect("bridge reflects external coil", snap.get("actuators", {}).get("conveyor_run") is True)
    expect("bridge reflects external setpoint", abs(snap.get("setpoints", {}).get("speed_setpoint", 0) - 5.0) < 0.01)

    result = _post("/api/integrations/modbus/stop", token=token)
    expect("admin stop ok", result.get("state") == "stopped")
    time.sleep(1)
    status = _get("/api/integrations", token=token)
    expect("modbus reports stopped", status["modbus"]["state"] == "stopped")
    client = ModbusTcpClient("127.0.0.1", port=502, timeout=3)
    expect("port closed after stop", client.connect() is False)
    client.close()

    result = _post("/api/integrations/modbus/start", token=token)
    expect("admin start ok", result.get("state") == "running", str(result))

    _post("/api/integrations/snapshot", token=token)
    activity = _get("/api/activity?limit=20", token=token)
    expect("snapshot lands in audit trail", any(a["action"] == "integration.snapshot" for a in activity))

    demo_token = _post("/api/auth/token", {"username": "demo@academy.local", "password": "demo1234"}, form=True)["access_token"]
    try:
        _post("/api/integrations/modbus/stop", token=demo_token)
        expect("non-admin cannot control links", False, "expected 403")
    except urllib.error.HTTPError as exc:
        expect("non-admin cannot control links", exc.code == 403)

    expect("s7 link reported disabled", status["s7"]["state"] == "disabled")
    expect("opcua link reported disabled", status["opcua"]["state"] == "disabled")
    expect("unauthenticated read blocked", _expect_401("/api/integrations"))

    print("integration_test: all checks passed")


def _expect_401(path):
    try:
        _get(path)
        return False
    except urllib.error.HTTPError as exc:
        return exc.code == 401


if __name__ == "__main__":
    main()