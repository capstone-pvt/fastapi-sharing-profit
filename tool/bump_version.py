"""Bump the API version in app/__init__.py and tag the commit.

Usage:
    python tool/bump_version.py patch    # 1.0.0 -> 1.0.1
    python tool/bump_version.py minor    # 1.0.1 -> 1.1.0
    python tool/bump_version.py major    # 1.1.0 -> 2.0.0
    python tool/bump_version.py 1.2.3    # explicit version

After running, push with:
    git push --follow-tags
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

INIT_FILE = Path(__file__).resolve().parents[1] / "app" / "__init__.py"
VERSION_RE = re.compile(r'__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"')


def read_version() -> str:
    text = INIT_FILE.read_text(encoding="utf-8")
    m = VERSION_RE.search(text)
    if not m:
        raise SystemExit(f"Could not find __version__ in {INIT_FILE}")
    return m.group(1)


def bump(current: str, kind: str) -> str:
    if kind == "explicit":
        return current  # caller passes resolved version
    major, minor, patch = (int(x) for x in current.split("."))
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise SystemExit(f"Unknown bump kind: {kind}")


def write_version(new_version: str) -> None:
    text = INIT_FILE.read_text(encoding="utf-8")
    new_text = VERSION_RE.sub(f'__version__ = "{new_version}"', text, count=1)
    INIT_FILE.write_text(new_text, encoding="utf-8")


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=INIT_FILE.parent.parent,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bump API version + tag commit.")
    parser.add_argument(
        "level",
        help="patch | minor | major | <explicit-version like 1.2.3>",
    )
    parser.add_argument(
        "--no-tag",
        action="store_true",
        help="Edit + commit but skip git tag.",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Edit only — no git commit, no tag.",
    )
    args = parser.parse_args()

    current = read_version()
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", args.level):
        new = args.level
    else:
        new = bump(current, args.level)

    print(f"  {current} -> {new}")
    write_version(new)
    print(f"  Wrote app/__init__.py")

    if args.no_commit:
        print("  --no-commit set: skipping git commit + tag.")
        return

    git("add", "app/__init__.py")
    git("commit", "-m", f"chore: release v{new}")
    print(f"  Committed: chore: release v{new}")

    if args.no_tag:
        print("  --no-tag set: skipping git tag.")
        return

    git("tag", "-a", f"v{new}", "-m", f"v{new}")
    print(f"  Tagged: v{new}")
    print()
    print("  Next: git push --follow-tags")


if __name__ == "__main__":
    sys.exit(main() or 0)
