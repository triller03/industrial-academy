"""Run every test suite against a live server. Usage: python tests/run_all.py (from backend/)."""
import subprocess
import sys
import urllib.request
from pathlib import Path

SUITES = ["smoke_test", "refresh_test", "offline_test", "admin_test", "generator_test", "frontend_static", "integration_test", "curriculum_test", "stats_test", "security_test", "billing_test", "licensing_test", "blueprint_test", "ai_test"]


def server_up() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> int:
    if not server_up():
        print("The API server is not running on http://127.0.0.1:8000.")
        print("From Visual Studio 2026 (or your terminal), start it with:")
        print("  Set-Location backend; .\\.venv\\Scripts\\python.exe run.py")
        return 2

    python = sys.executable
    results = []
    for name in SUITES:
        script = Path(__file__).parent / f"{name}.py"
        print(f"\n===== {name} =====")
        proc = subprocess.run([python, str(script)], cwd=Path(__file__).parent.parent)
        results.append((name, proc.returncode == 0))

    print("\n" + "=" * 60)
    all_ok = True
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        all_ok = all_ok and ok
    print("=" * 60)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())