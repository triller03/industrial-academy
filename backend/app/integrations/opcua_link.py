"""WinCC / SCADA link via OPC UA (asyncua).

Subscribes to a comma-separated list of node identifiers (``opcua_nodes``), e.g.
``ns=2;s=WaterTank.Level;ns=2;s=WaterTank.Pressure``, and mirrors their live
values into a snapshot that the admin UI shows.

Optional: enable with ``INTEGRATION_OPCUA_ENABLED=1``.
"""

from __future__ import annotations

import asyncio
import threading
import time

try:
    from asyncua import Client  # type: ignore

    OPCUA_OK = True
except Exception:  # pragma: no cover
    OPCUA_OK = False


class OPCUALink:
    """A polling OPC UA client for WinCC Runtime / SCADA tag monitoring."""

    def __init__(self, url: str = "opc.tcp://127.0.0.1:4840", nodes: str = "",
                 poll_seconds: float = 30.0):
        self.url = url
        self.nodes = [n.strip() for n in nodes.split(",") if n.strip()]
        self.poll = poll_seconds
        self._client = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.state = "disabled"
        self.detail = "asyncua not available" if not OPCUA_OK else "stopped"
        self._lock = threading.Lock()
        self._snapshot: dict = {}

    def probe(self) -> dict:
        if not OPCUA_OK:
            return {"ok": False, "detail": "asyncua is not installed"}
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
        try:
            result = self._loop.run_until_complete(self._read_once())
            return result
        except Exception as exc:
            self.state = "error"
            self.detail = f"cannot reach OPC UA at {self.url} ({exc})"
            return {"ok": False, "detail": self.detail}

    async def _read_once(self) -> dict:
        from asyncua import Client

        client = Client(self.url)
        client.session_timeout = 10_000
        await client.connect()
        try:
            values = {}
            for node_id in self.nodes:
                node = client.get_node(node_id)
                value = await node.read_value()
                values[node_id] = value
        finally:
            await client.disconnect()
        with self._lock:
            self._snapshot = values
            self.state = "running"
            self.detail = f"connected to OPC UA server {self.url}"
        return {"ok": True, "values": values}

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._snapshot)

    def start(self) -> None:
        if not OPCUA_OK:
            self.state = "error"
            self.detail = "asyncua is not installed"
            return
        if not self.nodes:
            self.state = "disabled"
            self.detail = "no OPC UA nodes configured (INTEGRATION_OPCUA_NODES)"
            return
        self._stop.clear()
        self.state = "starting"
        self._thread = threading.Thread(target=self._loop_run, daemon=True, name="opcua-link")
        self._thread.start()

    def _loop_run(self) -> None:
        failures = 0
        while not self._stop.is_set():
            result = self.probe()
            if not result.get("ok"):
                failures += 1
                with self._lock:
                    self.state = "offline"
                    self.detail = self.detail or "unreachable"
                time.sleep(min(60.0, self.poll + failures * 5))
                continue
            failures = 0
            time.sleep(self.poll)

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            self.state = "stopped"
            self.detail = "stopped by administrator"