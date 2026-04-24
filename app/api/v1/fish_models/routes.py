import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile

from app.deps import require_roles
from app.domain.fish_models.services import (
    build_create_model_payload,
    build_update_model_payload,
    build_upload_record,
)
from app.infrastructure.fish_models.repository import (
    activate_model as repo_activate_model,
    create_model as repo_create_model,
    get_active as repo_get_active,
    list_models as repo_list_models,
    update_model as repo_update_model,
)
from app.infrastructure.fish_models.storage import save_model_zip


router = APIRouter(prefix="/fish/models", tags=["fish-models"])


# In-memory tracker for the most recent regression retrain job. Resets on
# server restart, which is fine: after a restart the admin just reloads the
# page and can kick off a new job or trust the weight_model.joblib mtime.
_retrain_state: dict[str, Any] = {"status": "idle"}


def _weight_model_mtime(project_root: Path) -> str | None:
    weight_path = project_root / "app" / "models" / "weight" / "weight_model.joblib"
    if not weight_path.exists():
        return None
    return datetime.fromtimestamp(
        weight_path.stat().st_mtime, tz=timezone.utc
    ).isoformat()


@router.get("", dependencies=[Depends(require_roles("admin"))])
async def list_models():
    return await repo_list_models()


@router.get("/active", dependencies=[Depends(require_roles("admin"))])
async def get_active(model_type: str):
    return await repo_get_active(model_type)


@router.post("", dependencies=[Depends(require_roles("admin"))])
async def create_model(payload: dict[str, Any] = Body(...)):
    model_payload = build_create_model_payload(payload)
    return await repo_create_model(model_payload)


@router.post("/upload", dependencies=[Depends(require_roles("admin"))])
async def upload_model(
    modelType: str = Body(...),
    version: str = Body(...),
    isActive: str = Body("false"),
    description: str | None = Body(None),
    model: UploadFile = File(...),
):
    if not model:
        raise HTTPException(status_code=400, detail="Model zip file is required")

    zip_path = save_model_zip(modelType, version, model.file)
    record = build_upload_record(
        model_type=modelType,
        version=version,
        description=description,
        is_active=isActive == "true",
        model_path=str(zip_path),
    )
    return await repo_create_model(record)


@router.patch("/{model_id}", dependencies=[Depends(require_roles("admin"))])
async def update_model(model_id: str, payload: dict[str, Any] = Body(...)):
    model_payload = build_update_model_payload(payload)
    doc = await repo_update_model(model_id, model_payload)
    if not doc:
        raise HTTPException(status_code=404, detail="Model not found")
    return doc


@router.patch("/{model_id}/activate", dependencies=[Depends(require_roles("admin"))])
async def activate_model(model_id: str):
    doc = await repo_activate_model(model_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Model not found")
    return doc


@router.post("/retrain-regression", dependencies=[Depends(require_roles("admin"))])
async def retrain_regression():
    """Kick off weight + price regression retraining from approved training samples.

    Fires the full export + `train_regression_models.py` pipeline as a background
    subprocess (YOLO retraining is skipped). Returns immediately. Poll
    ``GET /fish/models/retrain-regression/status`` for progress.
    """
    global _retrain_state
    existing_proc = _retrain_state.get("_proc")
    if existing_proc is not None and existing_proc.poll() is None:
        raise HTTPException(
            status_code=409,
            detail="A retrain job is already running. Wait for it to finish or check the status endpoint.",
        )

    project_root = Path(__file__).resolve().parents[4]
    cmd = [
        sys.executable,
        "scripts/auto_train.py",
        "--skip-detect",
        "--skip-classify",
    ]
    env = dict(os.environ)
    # scripts/auto_train.py imports `app.db` etc., which requires the project
    # root on PYTHONPATH when invoked as a plain subprocess.
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(project_root) + (os.pathsep + existing_pp if existing_pp else "")
    )
    try:
        proc = subprocess.Popen(cmd, cwd=str(project_root), env=env)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to start retrain job: {exc}"
        )
    _retrain_state = {
        "status": "running",
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "pid": proc.pid,
        "weightModelMTimeAtStart": _weight_model_mtime(project_root),
        "_proc": proc,
    }
    return {
        "status": "started",
        "pid": proc.pid,
        "startedAt": _retrain_state["startedAt"],
    }


@router.get(
    "/retrain-regression/status",
    dependencies=[Depends(require_roles("admin"))],
)
async def retrain_regression_status():
    """Return the current/last regression retrain job state.

    States: idle | running | completed | failed.
    """
    global _retrain_state
    project_root = Path(__file__).resolve().parents[4]
    status = _retrain_state.get("status", "idle")

    proc = _retrain_state.get("_proc")
    if status == "running" and proc is not None:
        rc = proc.poll()
        if rc is not None:
            _retrain_state["status"] = "completed" if rc == 0 else "failed"
            _retrain_state["finishedAt"] = datetime.now(timezone.utc).isoformat()
            _retrain_state["exitCode"] = rc
            _retrain_state["weightModelMTime"] = _weight_model_mtime(project_root)
            _retrain_state.pop("_proc", None)
            status = _retrain_state["status"]

    return {
        "status": status,
        "startedAt": _retrain_state.get("startedAt"),
        "finishedAt": _retrain_state.get("finishedAt"),
        "pid": _retrain_state.get("pid"),
        "exitCode": _retrain_state.get("exitCode"),
        "weightModelMTimeAtStart": _retrain_state.get("weightModelMTimeAtStart"),
        "weightModelMTime": _weight_model_mtime(project_root),
    }


@router.delete("/{model_id}", dependencies=[Depends(require_roles("admin"))])
async def delete_model(
    model_id: str, status: str = Query("cancelled", pattern="^(cancelled|rejected)$")
):
    model_payload = build_update_model_payload(
        {"status": status, "isActive": False}
    )
    doc = await repo_update_model(model_id, model_payload)
    if not doc:
        raise HTTPException(status_code=404, detail="Model not found")
    return doc
