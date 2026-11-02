import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATA_DIR", _tmp)
os.environ.setdefault("DB_URL", f"sqlite:///{_tmp}/test.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.db import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CheckRun, Event, SOP, Step  # noqa: E402
from app.services import report  # noqa: E402


def _seed() -> int:
    init_db()
    with Session(engine) as s:
        sop = SOP(name="Report SOP", status="ready")
        s.add(sop)
        s.commit()
        s.refresh(sop)
        for i, a in enumerate(["Remove cap", "Remove screw", "Slide tray"], 1):
            s.add(Step(sop_id=sop.id, idx=i, action=a, critical=i > 1))
        # run A: clean
        a = CheckRun(sop_id=sop.id, status="done")
        # run B: step 2 flagged twice (one overridden), step 3 flagged once then pass
        b = CheckRun(sop_id=sop.id, status="done")
        c = CheckRun(sop_id=sop.id, status="active")
        s.add_all([a, b, c])
        s.commit()
        for k in (1, 2, 3):
            s.add(Event(run_id=a.id, step_idx=k, kind="pass", latency_s=18))
        s.add(Event(run_id=b.id, step_idx=1, kind="pass", latency_s=20))
        s.add(Event(run_id=b.id, step_idx=2, kind="flag", deviation_type="missing", reason="no screw shown",
                    latency_s=22))
        f2 = Event(run_id=b.id, step_idx=2, kind="flag", deviation_type="unclear", reason="blurry", latency_s=20)
        s.add(f2)
        s.commit()
        s.add(Event(run_id=b.id, step_idx=2, kind="override", observed_step_id=f2.id))
        s.add(Event(run_id=b.id, step_idx=3, kind="flag", deviation_type="wrong_order", reason="did step 2",
                    latency_s=20))
        s.add(Event(run_id=b.id, step_idx=3, kind="pass", latency_s=20))
        s.add(Event(run_id=c.id, step_idx=1, kind="flag", deviation_type="missing", reason="still wrapped",
                    latency_s=20))
        s.commit()
        return sop.id


def test_report_numbers():
    sop_id = _seed()
    with TestClient(app) as c:
        rep = c.get(f"/api/report?sop_id={sop_id}").json()
    k = rep["kpis"]
    assert k["runs"] == 3 and k["completed_runs"] == 2 and k["clean_runs"] == 1
    assert k["corrections"] == 4 and k["false_alarms"] == 1 and k["false_alarm_rate"] == 0.25
    # first attempts: A1 A2 A3 B1 pass, B2 B3 C1 flag -> 4/7
    assert k["first_try_pass_rate"] == round(4 / 7, 3)
    assert rep["most_failed_step"]["idx"] == 2 and rep["most_failed_step"]["flags"] == 2
    step2 = rep["per_step"][1]
    assert step2["flag_types"] == {"missing": 1, "unclear": 1} and step2["overrides"] == 1
    assert rep["deviation_types"][0] == {"type": "missing", "label": "Not finished", "count": 2}
    assert len(rep["recent_flags"]) == 4 and rep["recent_flags"][0]["step_idx"] == 1  # newest first
    assert sum(f["overridden"] for f in rep["recent_flags"]) == 1


def test_export_and_suggestions(monkeypatch):
    sop_id = _seed()
    fake = [{"step_idx": 2, "title": "Show the screw", "change": "Hold the removed screw to the camera",
             "why": "2 corrections on step 2"}]
    monkeypatch.setattr(report, "suggestions", lambda s, sid: fake)
    with TestClient(app) as c:
        sug = c.post("/api/report/suggestions", json={"sop_id": sop_id}).json()["suggestions"]
        assert sug == fake
        md = c.post("/api/report/export", json={"sop_id": sop_id, "suggestions": sug}).text
    assert md.startswith("# Shift report — Report SOP")
    assert "**Most-failed step:** 2. Remove screw — 2 corrections" in md
    assert "Step 2: Show the screw" in md
