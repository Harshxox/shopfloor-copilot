import os
import sys
from pathlib import Path

import tempfile  # noqa: E402

_tmp = tempfile.mkdtemp()
os.environ["DATA_DIR"] = _tmp
os.environ["DB_URL"] = f"sqlite:///{_tmp}/test.db"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.meta_client import parse_json, turns_as_text  # noqa: E402
from app.services.sam_parse import parse_frames, summary  # noqa: E402


def test_health():
    with TestClient(app) as c:
        r = c.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["models"]["spark"]


def test_empty_lists():
    with TestClient(app) as c:
        assert c.get("/api/sops").json() == []
        assert c.get("/api/sops/999").status_code == 404


def test_sam_parse_two_tracked_objects():
    text = (
        "<0f>0<|box;x1=75;y1=0;x2=495;y2=345;w=848;h=478|><|mask;x=0;y=0;data=1,1,~!|>"
        "<1f>0<|box;x1=75;y1=0;x2=471;y2=354;w=848;h=478|><|mask;x=0;y=0;data=1,1,~!|>"
        "1<|box;x1=576;y1=3;x2=847;y2=246;w=848;h=478|><|mask;x=0;y=0;data=1,1,~!|>"
    )
    frames = parse_frames(text)
    assert summary(frames) == {"n_frames": 2, "frames_per_object_id": {0: 2, 1: 1}}
    assert frames[1][1]["x1"] == 576


def test_parse_json_strips_fences():
    assert parse_json('```json\n{"steps": [1]}\n```') == {"steps": [1]}


def test_turns_as_text():
    assert turns_as_text([{"start_ms": 540, "end_ms": 2060, "text": "open the packet"}]) == \
        "[0.5-2.1s] open the packet"
