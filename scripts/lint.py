from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".json", ".toml"}
SKIP_PARTS = {".git", ".mypy_cache", ".pytest_cache", "dist", "build", "*.egg-info"}


def should_check(path: Path) -> bool:
    if path.suffix not in CHECK_SUFFIXES:
        return False
    return not any(part in SKIP_PARTS for part in path.parts)


def main() -> int:
    failures = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or not should_check(path):
            continue
        text = path.read_text(encoding="utf-8")
        if not text.endswith("\n"):
            failures.append(f"{path.relative_to(ROOT)}: missing final newline")
        for line_number, line in enumerate(text.splitlines(), 1):
            if line.rstrip() != line:
                failures.append(f"{path.relative_to(ROOT)}:{line_number}: trailing whitespace")
            if "\t" in line:
                failures.append(f"{path.relative_to(ROOT)}:{line_number}: tab character")
            if path.suffix == ".py" and len(line) > 120:
                failures.append(f"{path.relative_to(ROOT)}:{line_number}: Python line over 120 chars")
        if path.suffix == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                failures.append(f"{path.relative_to(ROOT)}:{exc.lineno}: invalid JSON: {exc.msg}")
    if failures:
        print("\n".join(failures))
        return 1
    print("lint ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
