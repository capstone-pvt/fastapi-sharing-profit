"""FastAPI application package."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Single source of truth for the API version. Bump via tool/bump_version.py.
__version__ = "1.0.0"


def _resolve_git_sha() -> str:
    """Return short git SHA — env (Railway) preferred, falling back to `git`.

    Railway exposes RAILWAY_GIT_COMMIT_SHA inside the container. Local dev
    has a working tree, so `git rev-parse` is fine. Returns 'unknown' if
    neither is available (e.g. a stripped Docker image without `git`).
    """
    sha = (
        os.environ.get("RAILWAY_GIT_COMMIT_SHA")
        or os.environ.get("GIT_COMMIT_SHA")
        or os.environ.get("RENDER_GIT_COMMIT")
    )
    if sha:
        return sha[:7]

    repo_root = Path(__file__).resolve().parents[1]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        return result.stdout.strip() or "unknown"
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return "unknown"


def _resolve_built_at() -> str:
    """Return build timestamp — Railway env preferred, else now()."""
    return (
        os.environ.get("RAILWAY_DEPLOYMENT_CREATED_AT")
        or os.environ.get("BUILT_AT")
        or datetime.now(timezone.utc).isoformat()
    )


# Computed once at import time — cheap, immutable for the process lifetime.
__git_sha__ = _resolve_git_sha()
__built_at__ = _resolve_built_at()


def build_info() -> dict:
    """Return version + build metadata as a JSON-serializable dict.

    Used by both `/health` and `/version` so the two endpoints can never drift.
    """
    return {
        "version": __version__,
        "gitSha": __git_sha__,
        "builtAt": __built_at__,
    }
