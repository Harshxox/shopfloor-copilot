"""Teach mode pipeline: expert video -> SOP with steps and thumbnails.

Runs in a background thread after upload. Each stage updates SOP.status so the UI can show progress:
  uploaded -> normalizing -> transcribing -> building -> thumbnails -> ready   (or failed + error)
Transcription and SAM highlights are best-effort: if they fail, the SOP is still built.
"""
import logging
from pathlib import Path

import cv2
from sqlmodel import Session, delete, select

from .. import config
from ..db import engine
from ..models import SOP, Step
from . import media, meta_client

log = logging.getLogger("teach")

BOX_COLORS = [(0, 200, 255), (255, 120, 0), (0, 220, 0), (200, 0, 200)]


def sop_dir(sop_id: int) -> Path:
    d = config.DATA_DIR / "sops" / str(sop_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def rel(path: Path) -> str:
    """Path relative to DATA_DIR, served by FastAPI at /media/<rel>."""
    return Path(path).relative_to(config.DATA_DIR).as_posix()


def _set(sop_id: int, **fields) -> None:
    with Session(engine) as s:
        sop = s.get(SOP, sop_id)
        for k, v in fields.items():
            setattr(sop, k, v)
        s.add(sop)
        s.commit()


def _highlight(img_path: Path, phrase: str) -> int:
    """Ask SAM 3.1 where `phrase` is in the keyframe and draw its boxes. Returns number of matches."""
    boxes = meta_client.sam_image(img_path, phrase)
    if not boxes:
        return 0
    img = cv2.imread(str(img_path))
    H, W = img.shape[:2]
    for b in boxes:
        sx, sy = W / b["w"], H / b["h"]
        p1, p2 = (int(b["x1"] * sx), int(b["y1"] * sy)), (int(b["x2"] * sx), int(b["y2"] * sy))
        color = BOX_COLORS[b["id"] % len(BOX_COLORS)]
        cv2.rectangle(img, p1, p2, color, 3)
        cv2.putText(img, phrase, (p1[0] + 4, max(p1[1] + 22, 22)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    cv2.imwrite(str(img_path), img)
    return len(boxes)


def run_teach(sop_id: int, upload_path: Path, use_sam: bool = True) -> None:
    d = sop_dir(sop_id)
    try:
        # 1. Normalise so every Meta API accepts it (H.264, <=720p, 10 fps, small)
        _set(sop_id, status="normalizing")
        video = media.normalize_video(upload_path, d / "video.mp4")
        _set(sop_id, video_path=rel(video))

        # 2. Transcribe narration (best-effort)
        transcript_text = ""
        if media.has_audio(upload_path):
            _set(sop_id, status="transcribing")
            try:
                wav = media.extract_wav(upload_path, d / "audio.wav")
                tr = meta_client.transcribe(wav)
                transcript_text = meta_client.turns_as_text(tr["turns"]) or tr["text"]
                _set(sop_id, transcript=transcript_text)
            except Exception as e:  # noqa: BLE001
                log.warning("SOP %s transcription failed, continuing without it: %s", sop_id, e)

        # 3. Spark builds the SOP from video + narration
        _set(sop_id, status="building")
        sop_json = meta_client.build_sop(video, transcript_text)

        with Session(engine) as s:
            sop = s.get(SOP, sop_id)
            if sop.name in ("", "Untitled SOP") and sop_json.get("task_name"):
                sop.name = sop_json["task_name"]
            s.exec(delete(Step).where(Step.sop_id == sop_id))
            for i, st in enumerate(sop_json["steps"], start=1):
                s.add(Step(
                    sop_id=sop_id, idx=i,
                    action=st.get("action", ""),
                    parts=list(st.get("parts") or []),
                    tools=list(st.get("tools") or []),
                    expected_end_state=st.get("expected_end_state", ""),
                    critical=bool(st.get("critical", False)),
                    start_sec=float(st.get("start_sec") or 0),
                    end_sec=float(st.get("end_sec") or 0),
                ))
            s.add(sop)
            s.commit()

        # 4. Keyframe per step (near the end = the step's finished state) + SAM highlight of its main part
        _set(sop_id, status="thumbnails")
        with Session(engine) as s:
            steps = s.exec(select(Step).where(Step.sop_id == sop_id).order_by(Step.idx)).all()
            for step in steps:
                at = max(step.start_sec, step.end_sec - 0.5)
                thumb = d / f"step_{step.idx}.jpg"
                try:
                    media.keyframe(video, thumb, at)
                    target = (step.parts or step.tools or [""])[0]
                    if use_sam and target:
                        try:
                            n = _highlight(thumb, target)
                            log.info("SOP %s step %s: SAM found %d x '%s'", sop_id, step.idx, n, target)
                        except Exception as e:  # noqa: BLE001
                            log.warning("SAM highlight failed for step %s: %s", step.idx, e)
                    step.thumbnail_path = rel(thumb)
                    s.add(step)
                except Exception as e:  # noqa: BLE001
                    log.warning("keyframe failed for step %s: %s", step.idx, e)
            s.commit()

        _set(sop_id, status="ready", error="")
        log.info("SOP %s ready", sop_id)
    except Exception as e:  # noqa: BLE001
        log.exception("SOP %s failed", sop_id)
        _set(sop_id, status="failed", error=str(e)[:500])
