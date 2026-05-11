#!/usr/bin/env python3
"""Validate every contract.md in the repo against schemas/contract.schema.json.

Usage:
  python3 scripts/validate-contracts.py [--strict] [paths...]

Exit code 0 on success, 1 on validation failure.

Skips chain files (frontmatter without `slug` and with `name` + numbered list body)
since they have a different shape. Skips files under .claude/goals/_archive/.

Requires: pyyaml, jsonschema. Install with:
  pip3 install --user pyyaml jsonschema
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
    import jsonschema
except ImportError as e:
    sys.stderr.write(f"Missing dependency: {e.name}. Run: pip3 install --user pyyaml jsonschema\n")
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "contract.schema.json"
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def extract_frontmatter(path: Path) -> dict | None:
    text = path.read_text()
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    try:
        return yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        # Surface the YAML error itself as a validation failure
        return {"__yaml_error__": str(e)}


def is_contract_candidate(fm: dict) -> bool:
    """Contracts must declare a `slug`. Files without it (chain files, skill
    files, anything else) are skipped — they have different shapes."""
    return "slug" in fm


def find_contracts(paths: list[Path]) -> list[Path]:
    if not paths:
        paths = [REPO_ROOT]
    seen: set[Path] = set()
    for p in paths:
        if p.is_file() and p.suffix == ".md":
            seen.add(p)
            continue
        for f in p.rglob("*.md"):
            if "_archive" in f.parts:
                continue
            if "node_modules" in f.parts:
                continue
            seen.add(f)
    return sorted(seen)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                        help="Treat skipped files (no frontmatter / chain files) as failures")
    parser.add_argument("paths", nargs="*", type=Path,
                        help="Files or directories to scan (default: whole repo)")
    args = parser.parse_args()

    schema = json.loads(SCHEMA_PATH.read_text())

    files = find_contracts(args.paths)
    if not files:
        print("No markdown files found.")
        return 0

    print(f"Validating {len(files)} markdown file(s) against contract.schema.json:\n")

    errors = 0
    for f in files:
        # Use repo-relative path for files inside REPO_ROOT (tidy output);
        # fall back to the absolute path for files outside the repo
        # (so the script can validate contracts in other repos when
        # given explicit paths via the CLI args).
        try:
            rel = f.relative_to(REPO_ROOT)
        except ValueError:
            rel = f
        fm = extract_frontmatter(f)

        if fm is None:
            if args.strict:
                errors += 1
                print(f"  [FAIL] {rel} — no frontmatter (strict mode)")
            else:
                print(f"  [skip] {rel} — no frontmatter")
            continue

        if isinstance(fm, dict) and "__yaml_error__" in fm:
            errors += 1
            print(f"  [FAIL] {rel} — YAML parse error:")
            for line in str(fm["__yaml_error__"]).splitlines():
                print(f"           {line}")
            continue

        if not is_contract_candidate(fm):
            if args.strict:
                errors += 1
                print(f"  [FAIL] {rel} — no `slug` field (strict mode rejects non-contracts)")
            else:
                print(f"  [skip] {rel} — no `slug` field (not a contract)")
            continue

        try:
            jsonschema.validate(fm, schema)
            print(f"  [PASS] {rel}")
        except jsonschema.ValidationError as e:
            errors += 1
            path = " > ".join(str(p) for p in e.absolute_path) or "(root)"
            print(f"  [FAIL] {rel}")
            print(f"           path: {path}")
            print(f"           msg:  {e.message}")

    print()
    if errors:
        print(f"{errors} file(s) failed validation.")
        return 1
    print("All contracts validate cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
