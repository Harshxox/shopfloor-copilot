"""Full Teach pipeline, offline: real ffmpeg on a synthetic video, Meta calls mocked."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["DATA_DIR"] = _tmp
os.environ["DB_URL"] = f"sqlite:///{_tmp}/test.db"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import media, meta_client  # noqa: E402

FAKE_SOP = {
    "task_name": "Disassemble M.2 enclosure",
    "steps": [
        {"id": 1, "action": "Remove the top end cap", "parts": ["end cap"], "tools": ["screwdriver"],
         "expected_end_state": "Cap detached", "critical": True, "start_sec": 0.0, "end_sec": 2.5},
        {"id": 2, "action": "Slide out the inner tray", "parts": ["inner tray"], "tools": [],
         "expected_end_state": "Tray outside housing", "critical": True, "start_sec": 2.5, "end_sec": 5.0},
    ],
}


@pytest.fixture()
def sample_video(tmp_path) -> Path:
    src = tmp_path / "expert.mp4"
    subprocess.run([media._ffmpeg(), "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25",
                    "-f", "lavfi", "-i", "sine=frequency=440",
                    "-t", "5", "-pix_fmt", "yuv420p", "-shortest", str(src)], check=True)
    return src


@pytest.fixture()
def mocked_meta(monkeypatch):
    calls = {"transcribe": 0, "build_sop": 0, "sam_image": 0}

    def fake_transcribe(wav, mode="ENDPOINTING"):
        calls["transcribe"] += 1
        return {"text": "remove the cap", "turns": [{"start_ms": 0, "end_ms": 2000, "text": "remove the cap"}]}

    def fake_build_sop(video, transcript="", attempts=2):
        calls["build_sop"] += 1
        assert "remove the cap" in transcript  # narration reaches Spark
        return FAKE_SOP

    def fake_sam_image(image, phrase):
        calls["sam_image"] += 1
        return [{"id": 0, "x1": 10, "y1": 10, "x2": 100, "y2": 100, "w": 640, "h": 360}]

    monkeypatch.setattr(meta_client, "transcribe", fake_transcribe)
    monkeypatch.setattr(meta_client, "build_sop", fake_build_sop)
    monkeypatch.setattr(meta_client, "sam_image", fake_sam_image)
    return calls


def test_teach_pipeline_end_to_end(sample_video, mocked_meta):
    with TestClient(app) as c:
        with sample_video.open("rb") as f:
            r = c.post("/api/sops/teach", files={"video": ("expert.mp4", f, "video/mp4")},
                       data={"name": ""})
        assert r.status_code == 202
        sop_id = r.json()["id"]

        body = c.get(f"/api/sops/{sop_id}").json()  # background task already ran in TestClient
        assert body["sop"]["status"] == "ready", body["sop"]["error"]
        assert body["sop"]["name"] == "Disassemble M.2 enclosure"
        assert body["sop"]["video_path"] == f"sops/{sop_id}/video.mp4"
        assert [s["action"] for s in body["steps"]] == ["Remove the top end cap", "Slide out the inner tray"]
        assert all(s["thumbnail_path"].endswith(".jpg") for s in body["steps"])
        assert mocked_meta == {"transcribe": 1, "build_sop": 1, "sam_image": 2}

        # thumbnails are served
        assert c.get(f"/media/{body['steps'][0]['thumbnail_path']}").status_code == 200

        # expert edits a step
        step_id = body["steps"][1]["id"]
        r = c.patch(f"/api/sops/{sop_id}/steps/{step_id}", json={"action": "Tilt and slide out the tray"})
        assert r.json()["action"] == "Tilt and slide out the tray"

        # delete
        assert c.delete(f"/api/sops/{sop_id}").status_code == 204
        assert c.get(f"/api/sops/{sop_id}").status_code == 404


def test_teach_marks_failed_when_spark_fails(sample_video, monkeypatch):
    monkeypatch.setattr(meta_client, "transcribe", lambda *a, **k: {"text": "", "turns": []})

    def boom(*a, **k):
        raise RuntimeError("Spark did not return a valid SOP")

    monkeypatch.setattr(meta_client, "build_sop", boom)
    with TestClient(app) as c:
        with sample_video.open("rb") as f:
            sop_id = c.post("/api/sops/teach", files={"video": ("e.mp4", f, "video/mp4")}).json()["id"]
        sop = c.get(f"/api/sops/{sop_id}").json()["sop"]
        assert sop["status"] == "failed"
        assert "valid SOP" in sop["error"]


def test_rejects_bad_file_type():
    with TestClient(app) as c:
        r = c.post("/api/sops/teach", files={"video": ("notes.txt", b"hi", "text/plain")})
        assert r.status_code == 400
