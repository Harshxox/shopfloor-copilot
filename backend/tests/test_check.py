"""Check mode engine, offline: real ffmpeg + OpenCV, Meta calls mocked."""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATA_DIR", _tmp)
os.environ.setdefault("DB_URL", f"sqlite:///{_tmp}/test.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.db import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import SOP, Step  # noqa: E402
from app.services import media, meta_client  # noqa: E402


@pytest.fixture()
def sop_id():
    init_db()
    with Session(engine) as s:
        sop = SOP(name="Enclosure", status="ready")
        s.add(sop)
        s.commit()
        s.refresh(sop)
        for i, a in enumerate(["Remove top end cap", "Remove bottom screw", "Slide out PCB tray"], 1):
            s.add(Step(sop_id=sop.id, idx=i, action=a, expected_end_state=f"{a} done", critical=True))
        s.commit()
        return sop.id


@pytest.fixture()
def clip(tmp_path) -> Path:
    p = tmp_path / "clip.webm"
    subprocess.run([media._ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "testsrc=size=640x360:rate=10", "-t", "2", "-c:v", "libvpx", str(p)], check=True)
    return p


@pytest.fixture()
def meta(monkeypatch):
    state = {"verdicts": [], "judge_langs": [], "translations": 0}

    monkeypatch.setattr(meta_client, "observe", lambda c: "Hands remove a cap.")
    monkeypatch.setattr(meta_client, "sam_track", lambda c, p: {
        i: [{"id": 0, "x1": 10, "y1": 10, "x2": 200, "y2": 200, "w": 640, "h": 360}] for i in range(20)})

    def judge(clip, sop_text, step_label, end_state, observation, language="en"):
        state["judge_langs"].append(language)
        assert "1. Remove top end cap" in sop_text and observation == "Hands remove a cap."
        return state["verdicts"].pop(0)

    def translate(actions, language):
        state["translations"] += 1
        return [f"[{language}] {a}" for a in actions]

    monkeypatch.setattr(meta_client, "judge", judge)
    monkeypatch.setattr(meta_client, "translate_steps", translate)
    return state


def _check(c, run_id, clip):
    with clip.open("rb") as f:
        return c.post(f"/api/runs/{run_id}/check", files={"clip": ("clip.webm", f, "video/webm")})


def test_full_run_pass_flag_override_done(sop_id, clip, meta):
    meta["verdicts"] = [
        {"verdict": "pass", "evidence": "cap off at 0:02"},
        {"verdict": "flag", "type": "skip", "observed_step_id": 3, "reason": "screw still in",
         "instruction_for_worker": "ಮೊದಲು ಸ್ಕ್ರೂ ತೆಗೆಯಿರಿ"},
        {"verdict": "pass", "evidence": "screw removed"},
        {"verdict": "pass", "evidence": "tray out"},
    ]
    with TestClient(app) as c:
        r = c.post("/api/runs", json={"sop_id": sop_id, "worker_language": "kn"})
        assert r.status_code == 201
        body = r.json()
        run_id = body["run"]["id"]
        assert body["say"] == "ಮೊದಲ ಹಂತ: [kn] Remove top end cap"

        # step 1 passes -> advance, next instruction in Kannada
        r = _check(c, run_id, clip).json()
        assert r["event"]["kind"] == "pass" and r["run"]["current_step"] == 2
        assert r["say"].startswith("ಸರಿ.") and "[kn] Remove bottom screw" in r["say"]
        assert r["overlay_pending"] is True and set(r["timings"]) >= {"observe_s", "judge_s", "total_s"}
        # SAM overlay is built in the background and attached to the event afterwards
        for _ in range(100):
            path = c.get(f"/api/runs/{run_id}").json()["events"][0]["clip_path"]
            if path.endswith("_hands.mp4"):
                break
            time.sleep(0.1)
        assert path.endswith("_hands.mp4")
        assert c.get(f"/media/{path}").status_code == 200

        # step 2 flagged -> stays on step 2, worker hears the correction
        r = _check(c, run_id, clip).json()
        assert r["event"]["kind"] == "flag" and r["event"]["deviation_type"] == "skip"
        assert r["run"]["current_step"] == 2
        assert r["say"] == "ಮೊದಲು ಸ್ಕ್ರೂ ತೆಗೆಯಿರಿ"

        # retry passes
        r = _check(c, run_id, clip).json()
        assert r["run"]["current_step"] == 3

        # last step -> done
        r = _check(c, run_id, clip).json()
        assert r["run"]["status"] == "done"
        assert "ಎಲ್ಲಾ ಹಂತಗಳು" in r["say"]
        assert _check(c, run_id, clip).status_code == 400  # can't check a finished run

        full = c.get(f"/api/runs/{run_id}").json()
        assert [e["kind"] for e in full["events"]] == ["pass", "flag", "pass", "pass"]
        assert meta["judge_langs"] == ["kn"] * 4
        assert meta["translations"] == 1  # translated once, then cached


def test_supervisor_override_advances(sop_id, clip, meta):
    meta["verdicts"] = [{"verdict": "flag", "type": "unclear", "observed_step_id": None,
                         "reason": "blurry", "instruction_for_worker": "Show the cap to the camera"}]
    with TestClient(app) as c:
        run_id = c.post("/api/runs", json={"sop_id": sop_id, "worker_language": "en"}).json()["run"]["id"]
        flag = _check(c, run_id, clip).json()["event"]
        r = c.post(f"/api/runs/{run_id}/override", json={"event_id": flag["id"]}).json()
        assert r["run"]["current_step"] == 2
        assert r["say"] == "Correct. Next: Remove bottom screw"
        kinds = [e["kind"] for e in c.get(f"/api/runs/{run_id}").json()["events"]]
        assert kinds == ["flag", "override"]


def test_sam_failure_does_not_block_judging(sop_id, clip, meta, monkeypatch):
    def boom(*a):
        raise RuntimeError("SAM down")
    monkeypatch.setattr(meta_client, "sam_track", boom)
    meta["verdicts"] = [{"verdict": "pass", "evidence": "ok"}]
    with TestClient(app) as c:
        run_id = c.post("/api/runs", json={"sop_id": sop_id}).json()["run"]["id"]
        r = _check(c, run_id, clip).json()
        assert r["event"]["kind"] == "pass"
        assert not r["event"]["clip_path"].endswith("_hands.mp4")


def test_delete_step_renumbers(sop_id):
    with TestClient(app) as c:
        steps = c.get(f"/api/sops/{sop_id}").json()["steps"]
        remaining = c.delete(f"/api/sops/{sop_id}/steps/{steps[0]['id']}").json()
        assert [s["idx"] for s in remaining] == [1, 2]
        assert remaining[0]["action"] == "Remove bottom screw"
