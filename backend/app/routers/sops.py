"""Teach mode endpoints."""
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, delete, select

from ..db import get_session
from ..models import SOP, Step
from ..services import teach

router = APIRouter()

ALLOWED = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".3gp"}


@router.get("")
def list_sops(session: Session = Depends(get_session)) -> list[SOP]:
    return list(session.exec(select(SOP).order_by(SOP.created_at.desc())))


@router.get("/{sop_id}")
def get_sop(sop_id: int, session: Session = Depends(get_session)) -> dict:
    sop = session.get(SOP, sop_id)
    if not sop:
        raise HTTPException(404, "SOP not found")
    steps = session.exec(select(Step).where(Step.sop_id == sop_id).order_by(Step.idx)).all()
    return {"sop": sop, "steps": steps}


@router.post("/teach", status_code=202)
def teach_sop(
    background: BackgroundTasks,
    video: UploadFile = File(..., description="Expert video (mp4/mov/webm), ideally with narration"),
    name: str = Form("Untitled SOP"),
    use_sam: bool = Form(True),
    session: Session = Depends(get_session),
) -> dict:
    """Upload an expert video. Returns immediately; poll GET /api/sops/{id} until status is ready/failed."""
    ext = Path(video.filename or "upload.mp4").suffix.lower() or ".mp4"
    if ext not in ALLOWED:
        raise HTTPException(400, f"Unsupported file type {ext}. Use one of {sorted(ALLOWED)}")

    sop = SOP(name=name or "Untitled SOP", status="uploaded")
    session.add(sop)
    session.commit()
    session.refresh(sop)

    dst = teach.sop_dir(sop.id) / f"original{ext}"
    with dst.open("wb") as f:
        shutil.copyfileobj(video.file, f)

    background.add_task(teach.run_teach, sop.id, dst, use_sam)
    return {"id": sop.id, "status": sop.status}


class StepUpdate(BaseModel):
    action: Optional[str] = None
    expected_end_state: Optional[str] = None
    critical: Optional[bool] = None
    parts: Optional[list[str]] = None
    tools: Optional[list[str]] = None


@router.patch("/{sop_id}/steps/{step_id}")
def update_step(sop_id: int, step_id: int, body: StepUpdate, session: Session = Depends(get_session)) -> Step:
    """Expert corrects a step the AI wrote."""
    step = session.get(Step, step_id)
    if not step or step.sop_id != sop_id:
        raise HTTPException(404, "Step not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(step, k, v)
    session.add(step)
    session.commit()
    session.refresh(step)
    return step


@router.delete("/{sop_id}", status_code=204)
def delete_sop(sop_id: int, session: Session = Depends(get_session)) -> None:
    sop = session.get(SOP, sop_id)
    if not sop:
        raise HTTPException(404, "SOP not found")
    session.exec(delete(Step).where(Step.sop_id == sop_id))
    session.delete(sop)
    session.commit()
    shutil.rmtree(teach.sop_dir(sop_id), ignore_errors=True)
