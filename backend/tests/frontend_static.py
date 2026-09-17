"""Static checks for the frontend: bracket balance (outside strings/comments) and ID references."""
import re
from pathlib import Path

root = Path(__file__).resolve().parents[2]
html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
css = (root / "frontend" / "css" / "styles.css").read_text(encoding="utf-8")
js_files = ["frontend/js/offline.js", "frontend/js/app.js", "frontend/sw.js"]

fail = False

REGEX_KEYWORDS = ("return", "typeof", "case", "in", "of", "new", "delete", "void",
                  "instanceof", "do", "else", "yield", "await", "throw")


def regex_allowed(prev: str, tail: str) -> bool:
    if prev == "":
        return True
    if prev in ")]}":
        return False
    if prev.isalnum() or prev in "_$":
        return any(tail.rstrip().endswith(k) for k in REGEX_KEYWORDS)
    return True


def strip_strings_and_comments(src: str) -> str:
    """Replace strings, template literals, regex literals and comments with placeholders."""
    out = []
    i, n = 0, len(src)
    prev = ""
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c == "/" and nxt == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                i += 1
            i += 2
            continue
        if c in "\"'":
            quote = c
            i += 1
            while i < n and src[i] != quote:
                if src[i] == "\\":
                    i += 1
                i += 1
            i += 1
            out.append("S")
            prev = "S"
            continue
        if c == "`":
            i += 1
            depth = 0
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == "$" and i + 1 < n and src[i + 1] == "{":
                    depth += 1
                    i += 2
                    continue
                if depth and src[i] == "}":
                    depth -= 1
                    i += 1
                    continue
                if depth == 0 and src[i] == "`":
                    i += 1
                    break
                i += 1
            out.append("T")
            prev = "T"
            continue
        if c == "/" and regex_allowed(prev, "".join(out)):
            i += 1
            in_class = False
            while i < n:
                ch = src[i]
                if ch == "\\":
                    i += 2
                    continue
                if ch == "[":
                    in_class = True
                elif ch == "]":
                    in_class = False
                elif ch == "/" and not in_class:
                    i += 1
                    break
                elif ch == "\n":
                    break
                i += 1
            while i < n and src[i].isalpha():
                i += 1
            out.append("R")
            prev = "R"
            continue
        out.append(c)
        if not c.isspace():
            prev = c
        i += 1
    return "".join(out)


for rel in js_files:
    src = (root / rel).read_text(encoding="utf-8")
    clean = strip_strings_and_comments(src)
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    ok = True
    for ch in clean:
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if not stack or stack.pop() != pairs[ch]:
                ok = False
                break
    if stack:
        ok = False
    print(f"{'PASS' if ok else 'FAIL'} syntax balance: {rel} (unclosed={''.join(stack)})")
    fail |= not ok

    names = re.findall(r"async function (\w+)", src) + re.findall(r"\nfunction (\w+)", src)
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        print(f"FAIL duplicate function definitions in {rel}: {sorted(dupes)}")
        fail = True

js = (root / "frontend/js/app.js").read_text(encoding="utf-8")
ids = set(re.findall(r'id="([^"]+)"', html))
refs = set(re.findall(r'\$\("#([A-Za-z0-9_-]+)"\)', js))
missing = sorted(refs - ids)
print(f"{'PASS' if not missing else 'FAIL'} element IDs referenced by app.js exist in index.html ({len(refs)} refs); missing={missing}")
fail |= bool(missing)

used = set()
for cls in re.findall(r'class="([^"]+)"', js):
    used.update(cls.split())
for cls in ["net-status", "online", "offline", "pending", "section-actions", "row", "ok", "warn", "dot"]:
    if cls in used:
        if not re.search(r"\." + re.escape(cls) + r"\b", css):
            print(f"WARN class '{cls}' used by JS but not styled in CSS")
        else:
            print(f"PASS class styled: .{cls}")

for asset in ["/index.html", "/css/styles.css", "/js/app.js", "/js/offline.js"]:
    exists = (root / "frontend" / asset.lstrip("/")).exists()
    print(f"{'PASS' if exists else 'FAIL'} shell asset exists: {asset}")
    fail |= not exists
reg_ok = "navigator.serviceWorker.register" in js
print(f"{'PASS' if reg_ok else 'FAIL'} app.js registers the service worker")
fail |= not reg_ok

print("\nFRONTEND STATIC:", "FAIL" if fail else "PASS")
raise SystemExit(1 if fail else 0)
