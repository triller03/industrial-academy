"""ASAP.A - Industrial Automation Training Platform (Windows desktop launcher).

Entry point for the PyInstaller bundle (see build-desktop.ps1). Starts the
FastAPI server on loopback, serves the bundled frontend, and hosts the UI in a
native WebView2 window (pywebview).

All user data (SQLite database, curriculum, offline packages) is stored under
%LOCALAPPDATA%\\IndustrialAcademy so an installer-user install stays writable and
survives app re-installs.

Environment overrides (useful for testing / fan-out):
    INDUSTRIAL_ACADEMY_DATA   base data directory (default %LOCALAPPDATA%\\IndustrialAcademy)
    INDUSTRIAL_ACADEMY_CONFIG  config file to load (default <data>\\config.env)
    INDUSTRIAL_ACADEMY_PORT   fixed port (default: a random free loopback port)
    INDUSTRIAL_ACADEMY_SMOKE  "1" = headless self-check, writes INDUSTRIAL_ACADEMY_SMOKE_FILE, exits
    INDUSTRIAL_ACADEMY_SMOKE_FILE  where the smoke result is written (default <data>\\smoke.json)
    INDUSTRIAL_ACADEMY_LOG    where the launch log is appended (default %TEMP%\\IndustrialAcademy-launch.log)

AI mentor over the internet:
    Create <data>\\config.env (a template is written there on first launch) with, e.g.:

        AI_PROVIDER=openrouter
        AI_API_KEY=sk-or-...

    The app then uses the live LLM whenever it has internet access and falls
    back to the built-in offline Socratic engine on errors or offline use.
    Any provider supported by the backend works (openai, anthropic, gemini,
    ollama, or any OpenAI-compatible endpoint via AI_BASE_URL). Real
    environment variables set on the machine take precedence over the file.
"""

from __future__ import annotations

import os
import socket
import sys
import tempfile
import threading
import time
import traceback
import urllib.request


def _log_path() -> str:
    return os.environ.get("INDUSTRIAL_ACADEMY_LOG") or os.path.join(
        tempfile.gettempdir(), "IndustrialAcademy-launch.log"
    )


def log(message: str) -> None:
    try:
        with open(_log_path(), "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')} {message}\n")
    except Exception:  # noqa: BLE001
        pass


def info(message: str) -> None:
    log(message)
    try:
        print(message)
    except Exception:  # noqa: BLE001
        pass


CONFIG_TEMPLATE = """\
# ASAP.A desktop AI mentor settings.
# This app keeps working fully offline with the built-in Socratic engine.
# To enable the live LLM mentor over the internet, fill in a provider + key:
#   AI_PROVIDER=openrouter            # openai | openrouter | anthropic | gemini | ollama
#   AI_API_KEY=sk-or-...              # your key for the chosen provider
#   AI_BASE_URL=                      # optional custom OpenAI-compatible endpoint
#   AI_MODEL=                         # optional model override (provider default when blank)
# Any line whose KEY can be set as an environment variable is honoured;
# environment variables set on the machine take precedence over this file.
"""


def _load_config_env() -> None:
    """Load a per-user <data>/config.env into the process environment (defaults only).

    Real environment variables always win; the file just fills the gaps so an
    installed app can pick up AI_* keys without touching the machine's env.
    """
    path = os.environ.get("INDUSTRIAL_ACADEMY_CONFIG") or os.path.join(_data_dir(), "config.env")
    if not os.path.exists(path):
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(CONFIG_TEMPLATE)
        except Exception as exc:  # noqa: BLE001
            log(f"could not write config template: {exc}")
        return
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip("'\"").strip()
                if key and value:
                    os.environ.setdefault(key, value)
        log(f"config.env loaded: {path}")
    except Exception as exc:  # noqa: BLE001
        log(f"config.env could not be read: {exc}")


def _data_dir() -> str:
    root = os.environ.get("INDUSTRIAL_ACADEMY_DATA")
    if root:
        return root
    return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "IndustrialAcademy")


def configure() -> None:
    """Set app env BEFORE any app module is imported."""
    # A --windowed PyInstaller app has no console, so sys.stdout/stderr are
    # None; uvicorn's log-config formatter calls sys.stdout.isatty() and would
    # crash at startup. Give them quiet file-like stand-ins.
    for attr in ("stdout", "stderr"):
        if getattr(sys, attr, None) is None:
            setattr(sys, attr, open(os.devnull, "w", encoding="utf-8"))
    data_dir = _data_dir()
    os.makedirs(data_dir, exist_ok=True)
    _load_config_env()
    os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(data_dir, "academy.db"))
    os.environ.setdefault("OFFLINE_PACKAGES_DIR", os.path.join(data_dir, "offline_packages"))
    # The desktop bundle ships without the factory/TIA/WinCC integration
    # libraries; keep the admin integrations view honest and never bind the
    # privileged Modbus port 502 by default.
    os.environ.setdefault("INTEGRATIONS_ENABLED", "false")
    os.environ.setdefault("SIMULATED_PLANT", "false")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_ready(url: str, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def smoke(server, thread, url: str) -> int:
    import json

    from app.main import FRONTEND_DIR

    result = {
        "status": None,
        "url": url,
        "version": None,
        "frontend": False,
        "database": None,
        "frontend_dir": str(FRONTEND_DIR),
        "frontend_exists": FRONTEND_DIR.exists(),
        "steps": [],
    }

    def get(path: str, label: str):
        try:
            with urllib.request.urlopen(url + path, timeout=5) as resp:
                body = resp.read()
                result["steps"].append([label, resp.status])
                return body
        except Exception as exc:  # noqa: BLE001
            result["steps"].append([label, f"{type(exc).__name__}: {exc}"])
            raise

    try:
        hb = json.loads(get("/api/health", "health"))
        result["version"] = hb.get("version")
        result["database"] = hb.get("environment")
        html = get("/", "root").decode("utf-8", errors="ignore")
        result["frontend"] = "<!doctype html" in html.lower() or "<html" in html.lower()
        result["status"] = "ok"
    except Exception as exc:  # noqa: BLE001
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        out = os.environ.get("INDUSTRIAL_ACADEMY_SMOKE_FILE") or os.path.join(_data_dir(), "smoke.json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(result, fh)
    return 0 if result.get("status") == "ok" and result.get("frontend") else 1


def main() -> int:
    try:
        return _main()
    except Exception:  # noqa: BLE001
        log("FATAL: " + traceback.format_exc().replace("\n", " | "))
        raise


def _main() -> int:
    configure()
    log("launcher: configured")
    port = int(os.environ.get("INDUSTRIAL_ACADEMY_PORT") or _free_port())
    url = f"http://127.0.0.1:{port}"

    # Imported after configure() so get_settings()/PACKAGE_DIR see our env.
    import uvicorn

    from app.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True, name="academy-server")
    thread.start()
    log(f"launcher: server thread on {url}")

    if not wait_ready(url):
        info("academy server failed to start")
        return 1
    log("launcher: server ready")

    if os.environ.get("INDUSTRIAL_ACADEMY_SMOKE") == "1":
        log("launcher: smoke mode")
        return smoke(server, thread, url)

    import webview

    webview.create_window(
        "ASAP.A - Industrial Automation Training Platform",
        url,
        width=1280,
        height=840,
        min_size=(1024, 680),
    )
    try:
        log("launcher: opening webview window")
        webview.start()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    sys.exit(main())