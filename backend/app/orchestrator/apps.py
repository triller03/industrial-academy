"""Desktop tool registry: detect installed TIA Portal / WinCC / Factory I/O.

These are real engineering applications that cannot run on every install. The
registry reports what is actually available on this machine so the orchestrator
can drive live tools when present and degrade to a simulated workspace when not.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# Common install locations — expanded with known PROGRAMFILES environment roots
# so the same registry works on 32-bit and 64-bit hosts.
TOOL_SPECS: list[dict] = {
    "tia": {
        "label": "TIA Portal",
        "kind": "TIA Openness / SCL bridge",
        "glob": ["Siemens/Automation/Portal V*", "TIA Portal V*", "Siemens/TIA Portal V*"],
        "detail": "Automates PLC engineering through the Openness API.",
    },
    "wincc": {
        "label": "WinCC Unified",
        "kind": "SCADA / HMI",
        "glob": ["Siemens/Automation/WinCC Unified*", "Siemens/Automation/WinCC*"],
        "detail": "Builds and runs Unified SCADA screens.",
    },
    "factoryio": {
        "label": "Factory I/O",
        "kind": "3D virtual plant",
        "glob": ["Factory IO/Factory IO.exe", "Factory I/O/Factory IO.exe", "Factory IO.exe"],
        "detail": "Runs the virtual plant the simulation engine talks to over Modbus TCP.",
    },
}


def _roots() -> list[Path]:
    roots = []
    for var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "ProgramW6432"):
        val = os.environ.get(var)
        if val:
            roots.append(Path(val))
    return list(dict.fromkeys(roots))


def _find_glob(proc: str) -> Path | None:
    for root in _roots():
        for candidate in _glob_candidates(root, proc):
            if candidate.exists():
                return candidate
    return None


def _glob_candidates(root: Path, proc: str) -> list[Path]:
    import glob as _glob

    out: list[Path] = []
    expanded = str(root / proc)
    for hit in _glob.glob(expanded) + _glob.glob(expanded.replace("V*", "*")):
        out.append(Path(hit))
    return out


def detect_tools(app_paths: str = "", mode: str = "simulate") -> dict:
    """Probe the machine for installed engineering tools.

    ``app_paths`` is an optional JSON map like {"tia": "C:\\\\TIA", "wincc": "...",
    "factoryio": "..."} that bypasses auto-detection. ``mode`` is one of
    "simulate" | "live" (raised by the engine based on settings).
    """
    overrides: dict = {}
    if app_paths:
        try:
            overrides = json.loads(app_paths)
        except Exception:
            overrides = {}

    detected: dict = {}
    for key, spec in TOOL_SPECS.items():
        path = overrides.get(key) or _find_glob(spec["glob"][0])
        entry = {
            "key": key,
            "label": spec["label"],
            "kind": spec["kind"],
            "detail": spec["detail"],
            "path": str(path) if path else "",
        }
        if mode == "live" and not path:
            entry["state"] = "unavailable"
            entry["detail"] = spec["detail"] + " Not installed — falling back to simulated workspace."
        elif path:
            entry["state"] = "installed"
        else:
            entry["state"] = "simulated"
            entry["detail"] = spec["detail"] + " Not detected — driving a simulated workspace."
        detected[key] = entry
    return detected