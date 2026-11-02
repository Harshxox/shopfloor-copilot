"""Shift report endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlmodel import Session

from ..db import get_session
from ..limits import meta_budget
from ..services import report

router = APIRouter()


@router.get("")
def get_report(sop_id: Optional[int] = None, session: Session = Depends(get_session)) -> dict:
    """KPIs, per-step results, corrections by type and recent flags with evidence."""
    return report.build(session, sop_id)


class SuggestBody(BaseModel):
    sop_id: int


@router.post("/suggestions", dependencies=[Depends(meta_budget)])
def get_suggestions(body: SuggestBody, session: Session = Depends(get_session)) -> dict:
    """Muse Spark proposes 3 SOP changes grounded in the correction data."""
    try:
        return {"suggestions": report.suggestions(session, body.sop_id)}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


class ExportBody(BaseModel):
    sop_id: int
    suggestions: list[dict] = []


@router.post("/export", response_class=PlainTextResponse)
def export_md(body: ExportBody, session: Session = Depends(get_session)) -> str:
    rep = report.build(session, body.sop_id)
    if not rep.get("sop"):
        raise HTTPException(404, "SOP not found")
    return report.markdown(rep, body.suggestions)
