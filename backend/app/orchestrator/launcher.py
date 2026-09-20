"""Launcher: start installed engineering tools or record a simulated action.

Launching real TIA Portal / WinCC / Factory I/O is only attempted when the tool
is installed on this machine AND the orchestrator is in live mode. Otherwise the
launcher returns a simulated result so the workflow is always demoable.
"""

from __future__ import annotations

import json
import subprocess
import time

from app.orchestrator.apps import TOOL_SPECS, detect_tools


def _installed_path(tools: dict, key: str) -> str | None:
    entry = tools.get(key)
    if entry and entry.get("state") == "installed" and entry.get("path"):
        return entry["path"]
    return None


def launch_tool(app_paths: str, mode: str, key: str, actions: list[str]) -> dict:
    """Launch (or simulate) a desktop engineering tool.

    ``actions`` is a list of tool-specific operation labels recorded in the
    result; it wires the launcher to what the caller intends to drive next.
    """
    tools = detect_tools(app_paths, mode)
    spec = TOOL_SPECS.get(key, {})
    started_at = time.time()

    if mode == "live":
        path = _installed_path(tools, key)
        if not path:
            return {
                "ok": False,
                "app": key,
                "label": spec.get("label", key),
                "mode": "live",
                "detail": f"{spec.get('label', key)} is not installed on this host.",
                "actions": actions,
            }
        result = _spawn(path, spec.get("label", key))
        result.update({"actions": actions, "elapsed_ms": int((time.time() - started_at) * 1000)})
        return result

    return {
        "ok": True,
        "app": key,
        "label": spec.get("label", key),
        "mode": "simulate",
        "detail": (
            f"Simulated {spec.get('label', key)} session. "
            "Install the tool on this host and set ORCHESTRATOR_MODE=live to drive it for real."
        ),
        "actions": actions,
        "elapsed_ms": int((time.time() - started_at) * 1000),
    }


def _spawn(path: str, label: str) -> dict:
    try:
        proc = subprocess.Popen([path])
        return {
            "ok": True,
            "app": label.lower(),
            "mode": "live",
            "detail": f"{label} launched (pid {proc.pid or 'n/a'}).",
            "pid": proc.pid,
        }
    except Exception as exc:  # pragma: no cover - environment-dependent
        return {
            "ok": False,
            "mode": "live",
            "detail": f"Failed to launch {label}: {exc}",
        }