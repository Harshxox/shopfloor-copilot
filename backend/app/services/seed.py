"""Demo seed: a ready SOP (video, thumbnails, steps) shipped inside the app.

Hosting free tiers wipe the disk on restart; importing the seed when the database is empty means a judge
opening the live link can start Check mode immediately.
"""
import json
import logging
import shutil
from pathlib import Path

from sqlmodel import Session, select

from .. import config
from ..db import engine
from ..models import SOP, Step

log = logging.getLogger("seed")

STEP_FIELDS = ("idx", "action", "parts", "tools", "expected_end_state", "critical", "start_sec", "end_sec")


def export_sop(sop_id: int, out: Path) -> Path:
    """Write sop.json + video + thumbnails for one SOP into `out`."""
    out.mkdir(parents=True, exist_ok=True)
    with Session(engine) as s:
        sop = s.get(SOP, sop_id)
        if not sop:
            raise ValueError(f"SOP {sop_id} not found")
        steps = list(s.exec(select(Step).where(Step.sop_id == sop_id).order_by(Step.idx)))
    data = {"name": sop.name, "transcript": sop.transcript, "video": None, "steps": []}
    if sop.video_path and (config.DATA_DIR / sop.video_path).exists():
        shutil.copy(config.DATA_DIR / sop.video_path, out / "video.mp4")
        data["video"] = "video.mp4"
    for st in steps:
        row = {k: getattr(st, k) for k in STEP_FIELDS}
        row["thumbnail"] = None
        if st.thumbnail_path and (config.DATA_DIR / st.thumbnail_path).exists():
            name = f"step_{st.idx}.jpg"
            shutil.copy(config.DATA_DIR / st.thumbnail_path, out / name)
            row["thumbnail"] = name
        data["steps"].append(row)
    (out / "sop.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def import_seed(seed_dir: Path) -> int:
    data = json.loads((seed_dir / "sop.json").read_text(encoding="utf-8"))
    with Session(engine) as s:
        sop = SOP(name=data["name"], transcript=data.get("transcript", ""), status="ready")
        s.add(sop)
        s.commit()
        s.refresh(sop)
        dst = config.DATA_DIR / "sops" / str(sop.id)
        dst.mkdir(parents=True, exist_ok=True)
        if data.get("video"):
            shutil.copy(seed_dir / data["video"], dst / "video.mp4")
            sop.video_path = f"sops/{sop.id}/video.mp4"
        for row in data["steps"]:
            thumb = ""
            if row.get("thumbnail"):
                shutil.copy(seed_dir / row["thumbnail"], dst / row["thumbnail"])
                thumb = f"sops/{sop.id}/{row['thumbnail']}"
            s.add(Step(sop_id=sop.id, thumbnail_path=thumb, **{k: row[k] for k in STEP_FIELDS}))
        s.add(sop)
        s.commit()
        log.info("Imported demo SOP '%s' as id %s", sop.name, sop.id)
        return sop.id


def import_if_empty() -> int | None:
    if not (config.SEED_DIR / "sop.json").exists():
        return None
    with Session(engine) as s:
        if s.exec(select(SOP)).first():
            return None
    try:
        return import_seed(config.SEED_DIR)
    except Exception as e:  # noqa: BLE001
        log.warning("Seed import failed: %s", e)
        return None
