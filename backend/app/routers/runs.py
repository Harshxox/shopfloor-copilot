"""Check mode endpoints."""
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from ..db import get_session
from ..limits import meta_budget
from ..models import CheckRun, Event
from ..services import check

router = APIRouter()


class StartRun(BaseModel):
    sop_id: int
    worker_language: str = "en"  # en | kn | hi


@router.post("", status_code=201, dependencies=[Depends(meta_budget)])
def start_run(body: StartRun, session: Session = Depends(get_session)) -> dict:
    """Start a worker run. Returns the first instruction to speak, plus every step in the worker's language."""
    try:
        return check.start_run(session, body.sop_id, body.worker_language)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("")
def list_runs(session: Session = Depends(get_session)) -> list[CheckRun]:
    return list(session.exec(select(CheckRun).order_by(CheckRun.created_at.desc())))


@router.get("/{run_id}")
def get_run(run_id: int, session: Session = Depends(get_session)) -> dict:
    run = session.get(CheckRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    events = session.exec(select(Event).where(Event.run_id == run_id).order_by(Event.created_at)).all()
    return {"run": run, "events": events,
            "step_texts": check.step_texts(session, run.sop_id, run.worker_language)}


@router.post("/{run_id}/check", dependencies=[Depends(meta_budget)])
def check_step(
    run_id: int,
    clip: UploadFile = File(..., description="Short clip of the worker doing the current step"),
    step_idx: Optional[int] = Form(None, description="Defaults to the run's current step"),
    use_sam: bool = Form(True),
    session: Session = Depends(get_session),
) -> dict:
    """Judge one step (~20 s): blind observation + SAM hand tracking in parallel, then the strict judge."""
    ext = Path(clip.filename or "clip.webm").suffix.lower() or ".webm"
    tmp = check.run_dir(run_id) / f"upload{ext}"
    with tmp.open("wb") as f:
        shutil.copyfileobj(clip.file, f)
    try:
        return check.check_step(session, run_id, tmp, step_idx, use_sam)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    finally:
        tmp.unlink(missing_ok=True)


class Override(BaseModel):
    event_id: int
    note: str = ""


@router.post("/{run_id}/override")
def override(run_id: int, body: Override, session: Session = Depends(get_session)) -> dict:
    """Supervisor marks a flag as a false alarm; the run moves to the next step."""
    try:
        return check.override(session, run_id, body.event_id, body.note)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
