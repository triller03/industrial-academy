"""Siemens S7 link via python-snap7.

The app reads a fixed tag map from data block ``db``:

* byte 0 bits 0..3  -> ``start``, ``running``, ``estop``, ``reset``
* byte 2 INT        -> ``level``      (scaled, /100)
* byte 4 INT        -> ``speed``      (scaled, /100)
* byte 6 INT        -> ``speed_setpoint`` (write target, scaled /100)

Optional: start it with ``s7_enabled=True`` in settings or ``INTEGRATION_S7_ENABLED=1``.
"""

from __future__ import annotations

import struct
import threading
import time

try:
    import snap7  # type: ignore

    SNAP7_OK = True
except Exception:  # pragma: no cover
    SNAP7_OK = False

TAG_BITS = ["start", "running", "estop", "reset"]


class S7Link:
    """A polling snap7 client that mirrors a small DAT (data block) into a snapshot."""

    def __init__(self, ip: str = "192.168.0.1", rack: int = 0, slot: int = 1, db: int = 1,
                 poll_seconds: float = 0.5):
        self.ip = ip
        self.rack = rack
        self.slot = slot
        self.db = db
        self.poll = poll_seconds
        self._client = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.state = "disabled"
        self.detail = "python-snap7 not available" if not SNAP7_OK else "stopped"
        self._lock = threading.Lock()
        self._snapshot: dict = {}

    def _build_client(self):
        import snap7

        client = snap7.client.Client()
        client.set_connection_type(1)  # PG connection type
        client.connect(self.ip, self.rack, self.slot)
        return client

    def probe(self) -> dict:
        """Single connection attempt; returns a fresh snapshot (also used by poll)."""
        if not SNAP7_OK:
            return {"ok": False, "detail": "python-snap7 is not installed"}
        try:
            if self._client is None:
                self._client = self._build_client()
            return self._read_once()
        except Exception as exc:
            self.state = "error"
            self.detail = f"cannot reach S7 {self.ip}:{self.rack}/{self.slot} ({exc})"
            return {"ok": False, "detail": self.detail}

    def _read_once(self) -> dict:
        data = self._client.db_read(self.db, 0, 10)
        bits = data[0]
        level = struct.unpack_from(">h", data, 2)[0] / 100.0
        speed = struct.unpack_from(">h", data, 4)[0] / 100.0
        setpoint = struct.unpack_from(">h", data, 6)[0] / 100.0
        values = {name: bool(bits & (1 << i)) for i, name in enumerate(TAG_BITS)}
        values.update({"level": level, "speed": speed, "speed_setpoint": setpoint})
        with self._lock:
            self._snapshot = values
            self.state = "running"
            self.detail = f"connected to S7 at {self.ip} (rack {self.rack}, slot {self.slot})"
        return {"ok": True, "values": values}

    def write_setpoint(self, value: float) -> bool:
        if self._client is None:
            return False
        raw = struct.pack(">h", int(round(value * 100)))
        self._client.db_write(self.db, 6, raw)
        return True

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._snapshot)

    def start(self) -> None:
        if not SNAP7_OK:
            self.state = "error"
            self.detail = "python-snap7 is not installed"
            return
        self._stop.clear()
        self.state = "starting"
        self._thread = threading.Thread(target=self._loop, daemon=True, name="s7-link")
        self._thread.start()

    def _loop(self) -> None:
        failures = 0
        while not self._stop.is_set():
            result = self.probe()
            if not result.get("ok"):
                failures += 1
                if result.get("detail"):
                    with self._lock:
                        self.state = "offline"
                        self.detail = result["detail"]
                time.sleep(min(5.0, 0.5 + failures * 2))
                continue
            failures = 0
            time.sleep(self.poll)

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            self.state = "stopped"
            self.detail = "stopped by administrator"
            if self._client is not None:
                try:
                    self._client.disconnect()
                except Exception:
                    pass
                self._client.destroy()
                self._client = None