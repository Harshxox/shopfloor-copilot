"""Check mode engine: a worker does the SOP, each step clip is judged by the Muse Spark agent.

Per step clip:
  normalize (ffmpeg) -> blind observe (Spark) -> strict judge (Spark agent) -> respond
  then, in the background: SAM 3.1 hand tracking -> overlay video attached to the event
  pass  -> event saved, run advances, worker hears "Correct. Next: <next step>"
  flag  -> event saved, run stays, worker hears the corrective instruction
Supervisor can override a flag (false alarm) -> run advances.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
from sqlmodel import Session, delete, select

from .. import config
from ..db import engine
from ..models import CheckRun, Event, SOP, Step, StepTranslation
from . import media, meta_client

log = logging.getLogger("check")

PHRASES = {
    "en": {"correct": "Correct.", "next": "Next:", "start": "Step 1:", "done": "All steps complete. Well done."},
    "kn": {"correct": "ಸರಿ.", "next": "ಮುಂದಿನ ಹಂತ:", "start": "ಮೊದಲ ಹಂತ:", "done": "ಎಲ್ಲಾ ಹಂತಗಳು ಮುಗಿದಿವೆ. ಚೆನ್ನಾಗಿದೆ."},
    "hi": {"correct": "सही।", "next": "अगला कदम:", "start": "पहला कदम:", "done": "सभी कदम पूरे हुए। बहुत बढ़िया।"},
}


def run_dir(run_id: int) -> Path:
    d = config.DATA_DIR / "runs" / str(run_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def rel(path: Path) -> str:
    return Path(path).relative_to(config.DATA_DIR).as_posix()


def _steps(s: Session, sop_id: int) -> list[Step]:
    return list(s.exec(select(Step).where(Step.sop_id == sop_id).order_by(Step.idx)))


def sop_text(steps: list[Step]) -> str:
    return "\n".join(f"{st.idx}. {st.action} -> done when: {st.expected_end_state}" for st in steps)


def step_texts(s: Session, sop_id: int, lang: str) -> dict[int, str]:
    """Step actions in the worker's language, translated once and cached. Falls back to English."""
    steps = _steps(s, sop_id)
    if lang == "en":
        return {st.idx: st.action for st in steps}
    cached = s.exec(select(StepTranslation).where(StepTranslation.sop_id == sop_id,
                                                  StepTranslation.lang == lang)).all()
    if len(cached) == len(steps):
        return {t.idx: t.text for t in cached}
    try:
        texts = meta_client.translate_steps([st.action for st in steps], lang)
    except Exception as e:  # noqa: BLE001
        log.warning("translation to %s failed, using English: %s", lang, e)
        return {st.idx: st.action for st in steps}
    s.exec(delete(StepTranslation).where(StepTranslation.sop_id == sop_id, StepTranslation.lang == lang))
    for st, t in zip(steps, texts):
        s.add(StepTranslation(sop_id=sop_id, lang=lang, idx=st.idx, text=t))
    s.commit()
    return {st.idx: t for st, t in zip(steps, texts)}


def start_run(s: Session, sop_id: int, lang: str) -> dict:
    sop = s.get(SOP, sop_id)
    if not sop or sop.status != "ready":
        raise ValueError("SOP not found or not ready")
    steps = _steps(s, sop_id)
    if not steps:
        raise ValueError("SOP has no steps")
    run = CheckRun(sop_id=sop_id, worker_language=lang if lang in PHRASES else "en")
    s.add(run)
    s.commit()
    s.refresh(run)
    texts = step_texts(s, sop_id, run.worker_language)
    p = PHRASES[run.worker_language]
    return {"run": run, "say": f"{p['start']} {texts[1]}", "step_texts": texts}


def _overlay_hands(clip: Path, out: Path) -> Path | None:
    """SAM 3.1 tracks the worker's hands through the clip; draw boxes so the supervisor sees the evidence."""
    frames = meta_client.sam_track(clip, "hand")
    if not frames:
        return None
    cap = cv2.VideoCapture(str(clip))
    fps = cap.get(cv2.CAP_PROP_FPS) or 10
    n_video = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    sam_fps = len(frames) / (n_video / fps)
    tmp = out.with_suffix(".raw.mp4")
    writer = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    colors = [(0, 200, 255), (255, 120, 0), (0, 220, 0)]
    i = 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        for o in frames.get(min(int(round(i / fps * sam_fps)), len(frames) - 1), []):
            sx, sy = W / o["w"], H / o["h"]
            c = colors[o["id"] % len(colors)]
            cv2.rectangle(img, (int(o["x1"] * sx), int(o["y1"] * sy)), (int(o["x2"] * sx), int(o["y2"] * sy)), c, 3)
            cv2.putText(img, f"hand {o['id']}", (int(o["x1"] * sx) + 4, int(o["y1"] * sy) + 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, c, 2)
        writer.write(img)
        i += 1
    cap.release()
    writer.release()
    media.reencode_h264(tmp, out)  # mp4v doesn't play in browsers; H.264 does
    tmp.unlink(missing_ok=True)
    return out


def check_step(s: Session, run_id: int, upload: Path, step_idx: int | None = None, use_sam: bool = True) -> dict:
    run = s.get(CheckRun, run_id)
    if not run:
        raise ValueError("run not found")
    if run.status == "done":
        raise ValueError("run already complete")
    steps = _steps(s, run.sop_id)
    idx = step_idx or run.current_step
    step = next((st for st in steps if st.idx == idx), None)
    if not step:
        raise ValueError(f"step {idx} not in SOP")

    t0 = time.perf_counter()
    timings = {}
    d = run_dir(run_id)
    n = len([p for p in d.glob(f"step{idx}_try*.mp4") if "_hands" not in p.name]) + 1
    clip = media.normalize_video(upload, d / f"step{idx}_try{n}.mp4")
    timings["normalize_s"] = round(time.perf_counter() - t0, 2)

    t = time.perf_counter()
    observation = meta_client.observe(clip)
    timings["observe_s"] = round(time.perf_counter() - t, 2)

    done_idx = sorted({e.step_idx for e in s.exec(select(Event).where(Event.run_id == run_id))
                       if e.kind in ("pass", "override") and e.step_idx != idx})
    completed = ", ".join(f"{st.idx}. {st.action}" for st in steps if st.idx in done_idx)
    t = time.perf_counter()
    verdict = meta_client.judge(
        clip, sop_text(steps), f"Step {step.idx}: {step.action}", step.expected_end_state,
        observation, run.worker_language, completed=completed,
    )
    timings["judge_s"] = round(time.perf_counter() - t, 2)
    latency = round(time.perf_counter() - t0, 2)
    timings["total_s"] = latency

    passed = verdict["verdict"] == "pass"
    ev = Event(
        run_id=run_id, step_idx=idx, kind="pass" if passed else "flag",
        deviation_type="" if passed else verdict.get("type", "unclear"),
        observed_step_id=verdict.get("observed_step_id"),
        reason=verdict.get("reason", ""), evidence=verdict.get("evidence", ""),
        instruction=verdict.get("instruction_for_worker", ""),
        observation=observation, clip_path=rel(clip), latency_s=latency,
    )
    s.add(ev)

    texts = step_texts(s, run.sop_id, run.worker_language)
    p = PHRASES[run.worker_language]
    if passed:
        say = _advance(run, idx, len(steps), texts, p)
    else:
        say = ev.instruction or texts.get(idx, step.action)
    s.add(run)
    s.commit()
    s.refresh(ev)
    s.refresh(run)

    # SAM hand-tracking evidence is not needed for the verdict: build it after responding.
    overlay_pending = False
    if use_sam:
        overlay_pending = True
        _executor.submit(_overlay_job, ev.id, clip, d / f"step{idx}_try{n}_hands.mp4")
    return {"event": ev, "run": run, "say": say, "critical": step.critical,
            "timings": timings, "overlay_pending": overlay_pending}


_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="sam-overlay")


def _overlay_job(event_id: int, clip: Path, out: Path) -> None:
    try:
        overlay = _overlay_hands(clip, out)
    except Exception as e:  # noqa: BLE001
        log.warning("SAM overlay for event %s failed: %s", event_id, e)
        return
    if overlay:
        with Session(engine) as s:
            ev = s.get(Event, event_id)
            if ev:
                ev.clip_path = rel(overlay)
                s.add(ev)
                s.commit()
        log.info("SAM overlay ready for event %s", event_id)


def _advance(run: CheckRun, idx: int, total: int, texts: dict[int, str], p: dict) -> str:
    if idx >= total:
        run.status = "done"
        run.current_step = total
        return f"{p['correct']} {p['done']}"
    run.current_step = idx + 1
    return f"{p['correct']} {p['next']} {texts[idx + 1]}"


def override(s: Session, run_id: int, event_id: int, note: str = "") -> dict:
    """Supervisor marks a flag as a false alarm: logged, and the run moves on."""
    run = s.get(CheckRun, run_id)
    flagged = s.get(Event, event_id)
    if not run or not flagged or flagged.run_id != run_id or flagged.kind != "flag":
        raise ValueError("flag event not found for this run")
    steps = _steps(s, run.sop_id)
    s.add(Event(run_id=run_id, step_idx=flagged.step_idx, kind="override",
                reason=note or "Supervisor marked as false alarm", observed_step_id=flagged.id))
    texts = step_texts(s, run.sop_id, run.worker_language)
    say = _advance(run, flagged.step_idx, len(steps), texts, PHRASES[run.worker_language])
    s.add(run)
    s.commit()
    s.refresh(run)
    return {"run": run, "say": say}
