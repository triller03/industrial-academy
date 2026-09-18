"""IntegrationManager: starts/stops the configured links and drives the simulated plant."""

from __future__ import annotations

import threading
import time
from collections import deque

from app.integrations.modbus_link import ModbusLink
from app.integrations.opcua_link import OPCUALink
from app.integrations.s7_link import S7Link


class IntegrationManager:
    """Owns the FACTORY I/O, S7 and WinCC links plus a small simulated plant."""

    def __init__(self, settings):
        self.settings = settings
        self.modbus: ModbusLink | None = None
        self.s7: S7Link | None = None
        self.opcua: OPCUALink | None = None
        self.events: deque = deque(maxlen=200)
        self._lock = threading.Lock()
        self._poll_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.state = "disabled"

    # ----- lifecycle ---------------------------------------------------
    def start(self) -> None:
        if not self.settings.integrations_enabled:
            self.state = "disabled"
            return
        self.state = "running"
        if self.settings.modbus_enabled:
            self.modbus = ModbusLink(
                host=self.settings.modbus_host,
                port=self.settings.modbus_port,
            )
            self.modbus.start()
        if self.settings.s7_enabled:
            self.s7 = S7Link(
                ip=self.settings.s7_ip,
                rack=self.settings.s7_rack,
                slot=self.settings.s7_slot,
                db=self.settings.s7_db,
            )
            self.s7.start()
        if self.settings.opcua_enabled:
            self.opcua = OPCUALink(
                url=self.settings.opcua_url,
                nodes=self.settings.opcua_nodes,
            )
            self.opcua.start()
        if self.settings.simulated_plant:
            self._stop.clear()
            self._poll_thread = threading.Thread(target=self._plant_loop, daemon=True, name="plant-sim")
            self._poll_thread.start()

    def stop(self) -> None:
        self._stop.set()
        for link in (self.modbus, self.s7, self.opcua):
            if link is not None:
                try:
                    link.stop()
                except Exception:
                    pass

    # ----- status ------------------------------------------------------
    def status(self) -> dict:
        result = {"state": self.state, "events": list(self.events)}
        for name, link in (
            ("modbus", self.modbus),
            ("s7", self.s7),
            ("opcua", self.opcua),
        ):
            entry = {"enabled": link is not None}
            if link is not None:
                entry.update({"state": link.state, "detail": link.detail})
                snap = link.snapshot()
                if snap:
                    entry["snapshot"] = snap
            else:
                entry.update({"state": "disabled", "detail": "disabled in settings"})
            result[name] = entry
        return result

    def json_status(self) -> dict:
        status = self.status()
        if "snapshot" in status.get("modbus", {}):
            status["modbus"]["snapshot"] = self._compact(status["modbus"]["snapshot"])
        return status

    @staticmethod
    def _compact(snapshot: dict) -> dict:
        return {
            k: v
            for k, v in snapshot.items()
            if k not in ("state", "detail", "error")
        }

    # ----- admin controls ----------------------------------------------
    def modbus_start(self) -> dict:
        if self.modbus is None:
            self.modbus = ModbusLink(
                host=self.settings.modbus_host,
                port=self.settings.modbus_port,
            )
        self.modbus.start()
        return {"state": self.modbus.state, "detail": self.modbus.detail}

    def modbus_stop(self) -> dict:
        if self.modbus is not None:
            self.modbus.stop()
        return {"state": self.modbus.state if self.modbus else "stopped"}

    # ----- simulated plant ---------------------------------------------
    def _plant_loop(self) -> None:
        import random

        level = 12.0
        speed = 0.0
        runtime = 0
        previous_estop = False
        previous_high = False
        while not self._stop.is_set():
            time.sleep(1.0)
            if self.modbus is None or self.modbus.state != "running":
                continue
            commands = self.modbus.read_commands()
            setpoint = commands.get("level_setpoint", 0.0)
            speed_target = commands.get("speed_setpoint", 0.0)
            level += 0.15 * (setpoint - level)
            speed += 0.10 * (speed_target - speed)
            runtime += 1
            part_at_station = bool(commands.get("sorter_activate") and (runtime % 6 == 0))
            estop = bool(commands.get("estop", False))
            running = bool(commands.get("conveyor_run", False) and not estop)

            self.modbus.write_sensors({
                "part_at_station": part_at_station,
                "tank_low": level < 20.0,
                "tank_high": level > 80.0,
                "quality_ok": True,
                "running_lamp": running,
            })
            self.modbus.write_measurements({
                "speed": speed,
                "level": level,
                "flow": level * 1.05,
                "temp": 21.0 + speed * 0.4,
                "pressure": 3.2 + level / 25.0,
                "runtime_s": runtime,
            })
            if estop and not previous_estop:
                self._event("estop_asserted", commands)
            if self.modbus.snapshot().get("sensors", {}).get("tank_high") and not previous_high:
                self._event("tank_high_reached", {"level": round(level, 1)})
            previous_estop = estop
            previous_high = running and level > 80.0

    def _event(self, kind: str, detail: dict) -> None:
        with self._lock:
            self.events.append({"t": time.time(), "kind": kind, "detail": detail})