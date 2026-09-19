"""IntegrationManager: starts/stops the configured links and drives the simulated plant."""

from __future__ import annotations

import threading
import time
from collections import deque

from app.integrations.modbus_link import ModbusLink
from app.integrations.opcua_link import OPCUALink
from app.integrations.s7_link import S7Link

FAILSAFE_ESTOP_SECONDS = 1.5


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
        self._estop = False
        self._estop_since: float | None = None
        self._watchdog_tick: float | None = None
        self._failsafe_was_active = False

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
        result = {"state": self.state, "events": list(self.events), "safety": self.safety()}
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

    def safety(self) -> dict:
        with self._lock:
            estop = self._estop
            estop_since = self._estop_since
            watchdog = self._watchdog_tick
            failsafe = estop and (watchdog is not None) and (time.time() - estop_since >= FAILSAFE_ESTOP_SECONDS)
        return {
            "estop": estop,
            "estop_since": estop_since,
            "failsafe_active": failsafe,
            "plant_simulating": bool(self.settings.simulated_plant),
            "watchdog_last_tick": watchdog,
            "policy": {
                "estop_deglitch_seconds": FAILSAFE_ESTOP_SECONDS,
                "on_estop": "plant simulation frozen, actuators decayed, interlock logged",
            },
        }

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
        level = 12.0
        speed = 0.0
        runtime = 0
        previous_estop = False
        previous_failsafe = False
        previous_high = False
        while not self._stop.is_set():
            time.sleep(1.0)
            if self.modbus is None or self.modbus.state != "running":
                continue
            self._watchdog_tick = time.time()

            commands = self.modbus.read_commands()
            estop = bool(commands.get("estop", False))

            with self._lock:
                self._estop = estop
                if estop:
                    self._estop_since = self._estop_since or time.time()
                    estop_since = self._estop_since
                else:
                    self._estop_since = None
                    estop_since = None
            failsafe = estop and estop_since is not None and (time.time() - estop_since) >= FAILSAFE_ESTOP_SECONDS

            if estop and not previous_estop:
                self._event("estop_asserted", commands)
            if failsafe and not previous_failsafe:
                self._event(
                    "failsafe_enabled",
                    {"reason": "estop held past deglitch", "decay": "speed->0, level frozen", "commands": commands},
                )
            if not estop and previous_estop:
                self._event("estop_released", commands)

            setpoint = commands.get("level_setpoint", 0.0)
            speed_target = commands.get("speed_setpoint", 0.0)
            if failsafe:
                level += 0.15 * (0.0 - level) * 0.15
                speed += 0.10 * (0.0 - speed) * 1.5
            else:
                level += 0.15 * (setpoint - level)
                speed += 0.10 * (speed_target - speed)
            runtime += 1
            part_at_station = bool(commands.get("sorter_activate") and (runtime % 6 == 0))
            running = bool(commands.get("conveyor_run", False) and not failsafe)

            self.modbus.write_sensors({
                "part_at_station": part_at_station if not failsafe else False,
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
            if self.modbus.snapshot().get("sensors", {}).get("tank_high") and not previous_high:
                self._event("tank_high_reached", {"level": round(level, 1)})
            previous_estop = estop
            previous_failsafe = failsafe
            previous_high = running and level > 80.0

    def _event(self, kind: str, detail: dict) -> None:
        with self._lock:
            self.events.append({"t": time.time(), "kind": kind, "detail": detail})