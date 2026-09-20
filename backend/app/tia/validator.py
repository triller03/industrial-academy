"""TIA Openness bridge helpers (blueprint: TIA Openness API bridge).

Real TIA Portal + Openness licensing cannot be exercised on every install, so
the bridge is split into:

  1. probe()          — reports whether a real TIA connector is reachable.
  2. validate_scl()   — deterministic "pre-compile" SCL gating that catches the
                        classic mistakes (unbalanced blocks, missing END_IF,
                        bad data types) BEFORE the project ever hits TIA.
  3. import_tags_csv()— validates a TIA-style CSV tag import against the IEC
                        61131-3 data-type and address contract shared with the
                        project's I/O list.

These run locally so students get a real TIA workflow even on machines with no
TIA Portal installed; the live connector degrades gracefully to disabled.
"""

from __future__ import annotations

import csv
import io
import re
import socket

from app.config import get_settings

IEC_DATA_TYPES = {
    "BOOL", "BYTE", "WORD", "DWORD", "CHAR", "STRING", "WSTRING",
    "INT", "DINT", "LINT", "SINT", "UINT", "UDINT", "ULINT", "USINT",
    "REAL", "LREAL", "TIME", "DATE", "TOD", "DT", "ARRAY", "STRUCT",
}

ADDRESS_RE = re.compile(r"^(I|Q|M)\s*(W|D|B)?\s*[0-9.]+$|^DB\d+\.(DBW|DBD|DBX\d*\.[0-9.]+)", re.IGNORECASE)
TAG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
BLOCK_RE = re.compile(r"^\s*(FUNCTION_BLOCK|FUNCTION|PROGRAM)\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.IGNORECASE)
END_BLOCK_RE = re.compile(r"^\s*END_(FUNCTION_BLOCK|FUNCTION|PROGRAM)\b", re.IGNORECASE)
BEGIN_RE = re.compile(r"^\s*(BEGIN|VAR_TEMP|VAR)\b", re.IGNORECASE)


def probe() -> dict:
    """Check whether a live TIA Openness connector is reachable."""
    settings = get_settings()
    if not settings.tia_openness_enabled:
        return {
            "ok": False,
            "available": False,
            "platform": "TIA Openness / SCL connector",
            "detail": "TIA Openness connector is disabled in settings. Upload SCL or run the "
                      "offline pre-compile validator instead — this installs cleanly with no TIA Portal.",
        }
    try:
        with socket.create_connection((settings.tia_openness_host, settings.tia_openness_port), timeout=2.0):
            return {
                "ok": True,
                "available": True,
                "platform": "TIA Openness / SCL connector",
                "detail": f"TIA connector reachable at {settings.tia_openness_host}:{settings.tia_openness_port}.",
            }
    except OSError:
        return {
            "ok": False,
            "available": False,
            "platform": "TIA Openness / SCL connector",
            "detail": "No TIA connector responded. TIA Portal + Openness licence are required on this host.",
        }


# ---------- SCL pre-compile validation ----------

_PAIR = [("(", ")"), ("[", "]"), ("BEGIN", "END_FUNCTION_BLOCK"), ("BEGIN", "END_FUNCTION"), ("BEGIN", "END_PROGRAM")]


def validate_scl(source: str) -> dict:
    """Rule-based pre-compile check against common SCL mistakes.

    Returns issues (severity/line/message), a 0-100 readiness score, and the
    blocks it identified. Educational, not a substitute for the TIA compiler.
    """
    lines = (source or "").splitlines()
    issues: list[dict] = []
    blocks: list[dict] = []
    current_block: dict | None = None

    def add(severity: str, line_no: int, message: str) -> None:
        issues.append({"severity": severity, "line": line_no, "message": message})

    depth_paren = 0
    depth_bracket = 0
    open_if = open_for = open_case = open_while = open_repeat = 0

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue

        m = BLOCK_RE.match(line)
        if m and current_block is not None:
            add("error", idx, "Nested block declaration inside an open block.")
        if m:
            current_block = {"name": m.group(2), "start": idx, "end": None}
            blocks.append(current_block)

        if END_BLOCK_RE.match(line):
            if current_block is not None:
                current_block["end"] = idx
                current_block.pop("start", None)
            else:
                add("error", idx, f"END_ block without a matching {line}.")
            current_block = None

        # unbalanced delimiters
        depth_paren += line.count("(") - line.count(")")
        depth_bracket += line.count("[") - line.count("]")

        # control-flow structure counters
        if re.search(r"\bIF\b", line):
            open_if += 1
        if re.search(r"\bFOR\b", line) and not line.startswith("//"):
            open_for += 1
        if re.search(r"\bCASE\b", line):
            open_case += 1
        if re.search(r"\bWHILE\b", line):
            open_while += 1
        if re.search(r"\bREPEAT\b", line):
            open_repeat += 1
        open_if -= line.count("END_IF")
        open_for -= line.count("END_FOR")
        open_case -= line.count("END_CASE")
        open_while -= line.count("END_WHILE")
        open_repeat -= line.count("UNTIL")

        # declaration/body hygiene
        if line.startswith(("VAR", "VAR_INPUT", "VAR_OUTPUT", "VAR_TEMP")) and "END_" not in line:
            if ":=" in line and "TYPE" not in line:
                add("error", idx, "Assignment ':=' inside a VAR declaration block.")

    if depth_paren != 0:
        add("warning", 0, "Unbalanced parentheses '(' / ')'.")
    if depth_bracket != 0:
        add("warning", 0, "Unbalanced array brackets '[' ']'.")

    checks = {
        "missing BEGIN": current_block is not None,
        "unterminated IF": open_if > 0,
        "unterminated FOR": open_for > 0,
        "unterminated CASE": open_case > 0,
        "unterminated WHILE": open_while > 0,
        "unterminated REPEAT": open_repeat > 0,
    }
    for label, present in checks.items():
        if present:
            add("error", 0, f"{label}{' before block ends' if label == 'missing BEGIN' else ''}.")

    errors = [i for i in issues if i["severity"] == "error"]
    score = max(0, 100 - len(errors) * 15 - len([i for i in issues if i["severity"] == "warning"]) * 5)
    if not lines:
        score = 0
    return {
        "ok": not errors,
        "score": score,
        "issues": issues,
        "blocks": blocks,
        "checked": len(lines),
        "note": "Pre-compile gate only — the TIA compiler is the source of truth.",
    }


# ---------- CSV tag import ----------

def import_tags_csv(name: str, text: str) -> dict:
    """Validate a TIA-style CSV tag import against the tag/address contract."""
    issues: list[dict] = []
    rows: list[dict] = []
    seen_tags: set[str] = set()
    try:
        reader = csv.DictReader(io.StringIO(text.strip()))
    except Exception as exc:  # pragma: no cover - csv rarely raises
        issues.append({"severity": "error", "line": 0, "message": f"CSV unreadable: {exc}"})
        return {"ok": False, "rows": 0, "issues": issues, "tags": [], "import_name": name}

    if reader.fieldnames is None:
        issues.append({"severity": "error", "line": 0, "message": "Empty CSV — expected header Tag,DataType,Address,Description."})
        return {"ok": False, "rows": 0, "issues": issues, "tags": [], "import_name": name}

    norm = {h.strip().lower(): h for h in reader.fieldnames if h}
    required = {"tag", "datatype", "address"}
    missing = sorted(required - set(norm))
    if missing:
        issues.append({"severity": "error", "line": 0, "message": f"Missing columns: {', '.join(missing)}. Have: {', '.join(reader.fieldnames)}."})
        return {"ok": False, "rows": 0, "issues": issues, "tags": [], "import_name": name}

    for lineno, raw in enumerate(reader, start=2):
        tag = (raw.get(norm["tag"]) or "").strip()
        dtype = (raw.get(norm["datatype"]) or "").strip().upper()
        address = (raw.get(norm["address"]) or "").strip()
        description = (raw.get(norm.get("description", "Description")) or "").strip()
        if not tag and not dtype and not address:
            continue
        level = "warning"
        if not tag:
            level = "error"
        elif tag in seen_tags:
            level = "warning"
            issues.append({"severity": "warning", "line": lineno, "message": f"Duplicate tag '{tag}' overrides earlier row."})
        seen_tags.add(tag) if tag else None

        base_type = dtype.split("[", 1)[0].strip()
        if base_type not in IEC_DATA_TYPES:
            issues.append({"severity": "error", "line": lineno, "message": f"'{tag}': unknown IEC 61131-3 data type '{dtype}'."})
        if not ADDRESS_RE.match(address):
            issues.append({"severity": "warning", "line": lineno, "message": f"'{tag}': address '{address}' does not match I/Q/M/DB .. pattern."})
        if tag and not TAG_RE.match(tag):
            issues.append({"severity": "error", "line": lineno, "message": f"'{tag}': invalid tag name (letters, digits, '_', '.', '-')."})

        rows.append({"tag": tag, "datatype": dtype, "address": address, "description": description})

    errors = [i for i in issues if i["severity"] == "error"]
    return {
        "ok": not errors,
        "import_name": name,
        "rows": len(rows),
        "valid_rows": len(rows),
        "issues": issues,
        "tags": rows,
        "standard": "IEC 61131-3 / TIA Portal",
    }