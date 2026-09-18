"""Modbus TCP server bridge.

FACTORY I/O connects to this server through its built-in ``Modbus TCP/IP Client``
driver, mapping the scene I/O to the register layout below.

FACTORY I/O semantics (Modbus client):
* digital inputs  (sensors)      -> it reads them from **Coils**
* digital outputs (actuators)    -> it writes them to **Coils**
* analog inputs   (measurements) -> it reads them from **Input Registers**
* analog outputs  (setpoints)    -> it writes them to **Holding Registers**
"""

from __future__ import annotations

import asyncio
import socket
import threading

try:
    from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
    from pymodbus.server import ServerAsyncStop, StartAsyncTcpServer

    PYMODBUS_OK = True
except Exception:  # pragma: no cover
    PYMODBUS_OK = False

SCALE = 100

# Coils written by FACTORY I/O (actuator commands) -> read by the app.
ACTUATOR_COILS = {
    0: "conveyor_run",
    1: "sorter_activate",
    2: "valve_inlet",
    3: "valve_outlet",
    4: "beacon",
    5: "siren",
    6: "drain_valve",
    7: "mode_auto",
}

# Coils written by the app (simulated plant sensors) -> read by FACTORY I/O.
SENSOR_COILS = {
    64: "part_at_load",
    65: "part_at_station",
    66: "tank_low",
    67: "tank_high",
    68: "feeder_empty",
    69: "quality_ok",
    70: "pressure_low",
    71: "level_mid",
    72: "positioned",
    73: "running_lamp",
}

# Holding registers written by FACTORY I/O (setpoints) -> read by the app.
SETPOINT_REGS = {
    0: "speed_setpoint",
    1: "level_setpoint",
    2: "temp_setpoint",
    3: "pressure_setpoint",
    4: "tool_timeout_s",
}

# Input registers written by the app (simulated measurements) -> read by FACTORY I/O.
MEASUREMENT_REGS = {
    0: "speed",
    1: "level",
    2: "flow",
    3: "temp",
    4: "pressure",
    5: "runtime_s",
}

COIL_COUNT = 128
REG_COUNT = 16


class ModbusLink:
    """A threaded FACTORY I/O-facing Modbus TCP server."""

    def __init__(self, host: str = "127.0.0.1", port: int = 502):
        self.host = host
        self.port = port
        self.store: ModbusSlaveContext | None = None
        self._context = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.state = "disabled"
        self.detail = "pymodbus not available" if not PYMODBUS_OK else "stopped"

    def _bind_check(self) -> bool:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            return True
        except OSError as exc:
            self.detail = f"cannot bind {self.host}:{self.port} ({exc})"
            return False
        finally:
            s.close()

    def start(self) -> None:
        if not PYMODBUS_OK:
            self.state = "error"
            self.detail = "pymodbus is not installed"
            return
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            if not self._bind_check():
                self.state = "error"
                return
            di = ModbusSequentialDataBlock(0, [0] * REG_COUNT)
            co = ModbusSequentialDataBlock(0, [0] * COIL_COUNT)
            hr = ModbusSequentialDataBlock(0, [0] * REG_COUNT)
            ir = ModbusSequentialDataBlock(0, [0] * REG_COUNT)
            self.store = ModbusSlaveContext(di=di, co=co, hr=hr, ir=ir)
            self._context = ModbusServerContext(slaves=self.store, single=True)
            self.state = "running"
            self.detail = f"listening on {self.host}:{self.port} (bridged to FACTORY I/O)"
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._serve, daemon=True, name="modbus-server")
            self._thread.start()

    def _serve(self) -> None:
        if self._loop is None:
            return
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(
                StartAsyncTcpServer(context=self._context, address=(self.host, self.port))
            )
        except Exception as exc:  # pragma: no cover
            with self._lock:
                self.state = "error"
                self.detail = str(exc)

    def stop(self) -> None:
        with self._lock:
            if not self._loop:
                self.state = "stopped"
                return
            try:
                future = asyncio.run_coroutine_threadsafe(ServerAsyncStop(), self._loop)
                future.result(timeout=5)
            except Exception:
                pass
            self.state = "stopped"
            self.detail = "stopped by administrator"

    def read_commands(self) -> dict:
        with self._lock:
            out = {}
            if not self.store:
                return out
            try:
                coils = self.store.getValues(0x01, 0, COIL_COUNT)
                for addr, name in ACTUATOR_COILS.items():
                    out[name] = bool(coils[addr])
                holding = self.store.getValues(0x03, 0, REG_COUNT)
                for addr, name in SETPOINT_REGS.items():
                    out[name] = holding[addr] / SCALE
            except Exception:
                pass
            return out

    def write_sensors(self, values: dict[str, bool]) -> None:
        with self._lock:
            if not self.store:
                return
            addr_by_name = {v: k for k, v in SENSOR_COILS.items()}
            for name, val in values.items():
                addr = addr_by_name.get(name)
                if addr is None:
                    continue
                self.store.setValues(0x05, addr, [1 if val else 0])

    def write_measurements(self, values: dict[str, float]) -> None:
        with self._lock:
            if not self.store:
                return
            addr_by_name = {v: k for k, v in MEASUREMENT_REGS.items()}
            for name, val in values.items():
                addr = addr_by_name.get(name)
                if addr is None:
                    continue
                self.store.setValues(0x04, addr, [int(round(val * SCALE))])

    def snapshot(self) -> dict:
        with self._lock:
            result = {"state": self.state, "detail": self.detail}
            if not self.store:
                return result
            try:
                coils = self.store.getValues(0x01, 0, COIL_COUNT)
                result["actuators"] = {name: bool(coils[addr]) for addr, name in ACTUATOR_COILS.items()}
                result["sensors"] = {name: bool(coils[addr]) for addr, name in SENSOR_COILS.items()}
                holding = self.store.getValues(0x03, 0, REG_COUNT)
                result["setpoints"] = {name: holding[addr] / SCALE for addr, name in SETPOINT_REGS.items()}
                inputs = self.store.getValues(0x04, 0, REG_COUNT)
                result["measurements"] = {name: inputs[addr] / SCALE for addr, name in MEASUREMENT_REGS.items()}
            except Exception as exc:
                result["error"] = str(exc)
            return result