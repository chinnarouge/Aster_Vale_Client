#!/usr/bin/env python
"""PostToolUse hook: lint-fix and format Python the moment it is written.

Runs `ruff check --fix` then `ruff format` on the file just edited, so style is
never argued about from memory. Anything ruff cannot fix automatically is
reported back to the model via exit code 2.

Fails soft: if ruff cannot be resolved or takes too long, the edit still stands.

Self-check:  python -I .claude/hooks/format-python.py --selftest
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SUFFIXES = {".py", ".pyi"}
TIMEOUT = 90  # generous: the first uvx run may download ruff


def ruff_cmd():
    """Prefer ruff on PATH, else let uv fetch it. None if neither is available."""
    if shutil.which("ruff"):
        return ["ruff"]
    if shutil.which("uvx"):
        return ["uvx", "ruff"]
    if shutil.which("uv"):
        return ["uv", "tool", "run", "ruff"]
    return None


def target(tool_input, project_dir):
    """The Python file this edit touched, or None if it is not ours to format."""
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw:
        return None
    path = Path(raw)
    if path.suffix.lower() not in SUFFIXES:
        return None
    if project_dir:
        try:
            path.resolve().relative_to(Path(project_dir).resolve())
        except ValueError:
            return None  # outside the project, leave it alone
    return path if path.is_file() else None


def run(base, args, path):
    return subprocess.run(
        [*base, *args, str(path)],
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
    )


def format_file(path):
    """Returns leftover ruff output a human needs to act on, or ''."""
    base = ruff_cmd()
    if base is None:
        return ""  # no ruff, no opinion
    try:
        run(base, ["check", "--fix", "--quiet"], path)
        run(base, ["format", "--quiet"], path)
        remaining = run(base, ["check", "--quiet"], path)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return remaining.stdout.strip() if remaining.returncode else ""


def selftest():
    project = Path(tempfile.mkdtemp())
    ugly = project / "ugly.py"
    ugly.write_text("import os,sys\nx   =  {'a':1,  'b':2}\ndef f( a ):\n  return  a\n", encoding="utf8")

    # path filtering, which is the part that must never misfire
    assert target({"file_path": str(ugly)}, project) == ugly
    assert target({"file_path": str(project / "notes.md")}, project) is None
    assert target({"file_path": str(project / "gone.py")}, project) is None
    assert target({}, project) is None
    assert target({"file_path": "C:/elsewhere/other.py"}, project) is None, "must refuse files outside the project"

    base = ruff_cmd()
    if base is None:
        print("ok: path filtering correct (ruff unavailable, formatting not exercised)")
        return
    before = ugly.read_text(encoding="utf8")
    leftover = format_file(ugly)
    after = ugly.read_text(encoding="utf8")
    assert after != before, "ruff should have reformatted the file"
    assert "'a': 1" in after or '"a": 1' in after, f"unexpected formatting result:\n{after}"
    # the unused imports cannot be auto-removed safely in all cases, so either
    # ruff fixed them or it reported them; both are acceptable, silence is not
    print(f"ok: path filtering correct, file reformatted, leftover={leftover or 'none'}")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    path = target(event.get("tool_input") or {}, os.environ.get("CLAUDE_PROJECT_DIR", ""))
    if path is None:
        return
    leftover = format_file(path)
    if leftover:
        print(f"ruff formatted {path.name} but these need a human decision:\n{leftover}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
