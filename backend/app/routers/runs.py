"""Check mode endpoints. Phase 2: list/get only. Phase 5 adds start run + check step."""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import CheckRun, Event

router = APIRouter()


@router.get("")
def list_runs(session: Session = Depends(get_session)) -> list[CheckRun]:
    return list(session.exec(select(CheckRun).order_by(CheckRun.created_at.desc())))


@router.get("/{run_id}")
def get_run(run_id: int, session: Session = Depends(get_session)) -> dict:
    run = session.get(CheckRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    events = session.exec(select(Event).where(Event.run_id == run_id).order_by(Event.created_at)).all()
    return {"run": run, "events": events}
