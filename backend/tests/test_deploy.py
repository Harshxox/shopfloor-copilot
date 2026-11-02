"""Deploy features: demo seed round-trip, rate limits, SPA serving."""
import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATA_DIR", _tmp)
os.environ.setdefault("DB_URL", f"sqlite:///{_tmp}/test.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app import config, limits  # noqa: E402
from app.db import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import SOP, Step  # noqa: E402
from app.services import seed  # noqa: E402


def test_seed_round_trip(tmp_path):
    init_db()
    with Session(engine) as s:
        sop = SOP(name="Seed me", status="ready", video_path="")
        s.add(sop)
        s.commit()
        s.refresh(sop)
        d = config.DATA_DIR / "sops" / str(sop.id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "video.mp4").write_bytes(b"vid")
        (d / "step_1.jpg").write_bytes(b"img")
        sop.video_path = f"sops/{sop.id}/video.mp4"
        s.add(Step(sop_id=sop.id, idx=1, action="Do it", parts=["cap"], expected_end_state="done",
                   critical=True, thumbnail_path=f"sops/{sop.id}/step_1.jpg"))
        s.add(sop)
        s.commit()
        sid = sop.id
    out = seed.export_sop(sid, tmp_path / "seed")
    assert sorted(p.name for p in out.iterdir()) == ["sop.json", "step_1.jpg", "video.mp4"]
    new_id = seed.import_seed(out)
    with Session(engine) as s:
        new = s.get(SOP, new_id)
        st = s.exec(select(Step).where(Step.sop_id == new_id)).one()
    assert new.status == "ready" and new.name == "Seed me"
    assert (config.DATA_DIR / new.video_path).read_bytes() == b"vid"
    assert st.parts == ["cap"] and st.critical and (config.DATA_DIR / st.thumbnail_path).read_bytes() == b"img"


def test_rate_limit_per_ip(monkeypatch):
    limits.reset()
    monkeypatch.setattr(config, "RATE_PER_IP_HOUR", 2)
    with TestClient(app) as c:
        codes = [c.post("/api/runs", json={"sop_id": 999999}).status_code for _ in range(3)]
    assert codes[:2] == [400, 400]  # allowed through (then rejected: SOP missing)
    assert codes[2] == 429
    limits.reset()


def test_spa_served_when_built(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<div id=root></div>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    monkeypatch.setattr(config, "FRONTEND_DIST", str(dist))
    import importlib

    import app.main as main
    importlib.reload(main)
    with TestClient(main.app) as c:
        assert c.get("/check").text == "<div id=root></div>"          # client-side route -> index.html
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/api/health").json()["status"] == "ok"           # API still wins
        assert c.get("/api/nope").status_code == 404
