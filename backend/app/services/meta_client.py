"""Single wrapper for every Meta Model API call, built from the Phase 1 spikes.

- build_sop(video)            Muse Spark: expert video (+ transcript) -> SOP steps
- observe(clip)               Muse Spark: blind description of a clip (no expected step given)
- judge(clip, ...)            Muse Spark agent: pass_step / flag_deviation tool call
- sam_track(video, phrase)    SAM 3.1: per-frame boxes with stable object IDs
- transcribe(wav)             Muse Voice Transcribe: timed turns

Lessons baked in from SPIKES.md:
- video only via Responses API (input_video); muse-spark-1.2 for audio
- no strict json_schema (returned empty lists) -> prompt JSON + parse + retry
- tool_choice only "auto" -> system prompt forces one tool call
- judge sees a BLIND observation to avoid confirmation bias
"""
import base64
import json
import logging
import re
import time
import uuid
from pathlib import Path

import requests
from openai import OpenAI

from .. import config
from .sam_parse import parse_frames

log = logging.getLogger("meta")

_client: OpenAI | None = None


def client() -> OpenAI:
    """Meta Model API speaks the OpenAI wire format; requests go to api.meta.ai with the Meta key."""
    global _client
    if _client is None:
        if not config.MODEL_API_KEY:
            raise RuntimeError("MODEL_API_KEY is not set")
        _client = OpenAI(base_url=config.META_BASE_URL, api_key=config.MODEL_API_KEY,
                         timeout=config.REQUEST_TIMEOUT_S, max_retries=config.MAX_RETRIES)
    return _client


def _video_url(path: Path) -> str:
    return "data:video/mp4;base64," + base64.b64encode(Path(path).read_bytes()).decode()


def _timed(name: str):
    class _T:
        def __enter__(self):
            self.t0 = time.perf_counter()
            return self

        def __exit__(self, *exc):
            self.s = round(time.perf_counter() - self.t0, 2)
            log.info("%s took %.2fs%s", name, self.s, " (failed)" if exc[0] else "")
    return _T()


def parse_json(text: str) -> dict:
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])


# ---------- Teach mode ----------

SOP_PROMPT = (
    "You are an industrial engineer writing a standard operating procedure (SOP).\n"
    "Watch this whole video from start to end.{transcript_hint}\n"
    "List the steps that CHANGE THE STATE OF THE PRODUCT, in order: something is removed, attached, "
    "inserted, tightened, loosened, opened, closed, slid or connected. Typically 3 to 10 steps.\n"
    "Rules:\n"
    "- Do NOT include preparation or presentation as steps: picking up or putting down a tool, "
    "holding the object up, showing parts to the camera, inspecting without changing anything.\n"
    "- Unpacking from packaging counts only if the product is actually taken out.\n"
    "- Repeated actions on different parts are separate steps (e.g. 'Remove first bottom screw', "
    "'Remove second bottom screw').\n"
    "- One step = one visible change. A step must be checkable from its end state alone.\n"
    "- Do not return an empty list. Trust what you SEE over what is said if they disagree.\n"
    "For each step give: id, action (imperative, e.g. 'Remove the top screw'), parts, tools, "
    "expected_end_state (what it visibly looks like when done), critical (true if skipping it causes a "
    "defect or safety risk), start_sec and end_sec.\n"
    "Return ONLY a JSON object, no markdown fences, in exactly this shape:\n"
    '{{"task_name": "string", "steps": [{{"id": 1, "action": "string", "parts": ["string"], '
    '"tools": ["string"], "expected_end_state": "string", "critical": true, "start_sec": 0.0, "end_sec": 5.0}}]}}'
)


def build_sop(video: Path, transcript: str = "", attempts: int = 2) -> dict:
    hint = f"\nThe expert's narration (with timing) was:\n{transcript}" if transcript else ""
    prompt = SOP_PROMPT.format(transcript_hint=hint)
    last_err: Exception | None = None
    for attempt in range(1, attempts + 1):
        with _timed(f"build_sop try{attempt}"):
            resp = client().responses.create(
                model=config.SPARK_MODEL,
                input=[{"role": "user", "content": [
                    {"type": "input_video", "video_url": _video_url(video)},
                    {"type": "input_text", "text": prompt},
                ]}],
                reasoning={"effort": "medium"},
                max_output_tokens=8000,
            )
        try:
            sop = parse_json(resp.output_text)
            if sop.get("steps"):
                return sop
            last_err = ValueError("empty steps")
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
        log.warning("build_sop attempt %d invalid: %s", attempt, last_err)
    raise RuntimeError(f"Spark did not return a valid SOP: {last_err}")


# ---------- Check mode ----------

OBSERVE_PROMPT = (
    "Describe exactly what the person's hands do in this clip, in order, with approximate timestamps. "
    "Then describe the final state of the object in the last 2 seconds. "
    "Only report what is visible. Do not guess intentions or what happens next."
)

JUDGE_SYSTEM = (
    "You are a strict quality inspector on an assembly line. Your default answer is to FLAG. "
    "Call pass_step only if the clip visibly shows the expected action AND the expected end state is "
    "reached by the end of the clip. Narration alone is not proof; a similar-looking action on a different "
    "part is not proof. If the clip shows a different SOP step, flag wrong_order and give its id. "
    "If you cannot see it clearly, flag unclear. Call exactly one tool. "
    "instruction_for_worker is SPOKEN ALOUD to the worker: write it in {language}, ONE short sentence, "
    "at most 12 words, only what to do now (e.g. 'Remove the second bottom screw first.'). "
    "No step numbers, no explanation — the reason field is for the supervisor."
)

JUDGE_TOOLS = [
    {
        "type": "function",
        "name": "pass_step",
        "description": "ONLY when the clip visibly shows the expected step performed AND its end state reached.",
        "parameters": {
            "type": "object",
            "properties": {"evidence": {"type": "string"}},
            "required": ["evidence"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "flag_deviation",
        "description": "When the expected step is not visibly completed, a different step was done, or it's unclear.",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["skip", "wrong_order", "wrong_part", "missing", "unclear"]},
                "observed_step_id": {"type": ["integer", "null"]},
                "reason": {"type": "string"},
                "instruction_for_worker": {"type": "string",
                                           "description": "Spoken to the worker: one sentence, max 12 words."},
            },
            "required": ["type", "observed_step_id", "reason", "instruction_for_worker"],
            "additionalProperties": False,
        },
    },
]

LANG_NAMES = {"en": "English", "kn": "Kannada", "hi": "Hindi"}


def observe(clip: Path) -> str:
    with _timed("observe"):
        resp = client().responses.create(
            model=config.SPARK_MODEL,
            reasoning={"effort": "low"},
            input=[{"role": "user", "content": [
                {"type": "input_video", "video_url": _video_url(clip)},
                {"type": "input_text", "text": OBSERVE_PROMPT},
            ]}],
        )
    return resp.output_text


def judge(clip: Path, sop_text: str, step_label: str, end_state: str,
          observation: str, language: str = "en") -> dict:
    """Returns {"verdict": "pass"|"flag", ...tool args}. Malformed/no tool call -> flag 'unclear'."""
    text = (
        f"Full SOP:\n{sop_text}\n\n"
        f"Expected step for this clip: {step_label}\n"
        f"Expected end state: {end_state}\n\n"
        f"Independent observation of the clip (written without knowing the expected step):\n{observation}\n\n"
        "Check the video yourself as well, then call exactly one tool."
    )
    with _timed("judge"):
        resp = client().responses.create(
            model=config.SPARK_MODEL,
            instructions=JUDGE_SYSTEM.format(language=LANG_NAMES.get(language, "English")),
            input=[{"role": "user", "content": [
                {"type": "input_video", "video_url": _video_url(clip)},
                {"type": "input_text", "text": text},
            ]}],
            tools=JUDGE_TOOLS,
            tool_choice="auto",
        )
    for item in resp.output:
        if getattr(item, "type", "") != "function_call":
            continue
        try:
            args = json.loads(item.arguments)
        except json.JSONDecodeError:
            break
        if item.name == "pass_step":
            return {"verdict": "pass", **args}
        if item.name == "flag_deviation":
            return {"verdict": "flag", **args}
    return {"verdict": "flag", "type": "unclear", "observed_step_id": None,
            "reason": "Agent returned no valid tool call; needs supervisor review.",
            "instruction_for_worker": "", "raw_text": resp.output_text}


def translate_steps(actions: list[str], language: str) -> list[str]:
    """Translate short imperative step instructions for spoken use on the shop floor."""
    lang = LANG_NAMES.get(language, "English")
    prompt = (
        f"Translate these assembly instructions into simple spoken {lang} for a factory worker. "
        "Keep each one short and imperative. Keep part names a worker would say in English "
        "(e.g. screw, PCB, USB) as they are commonly spoken. "
        f"Return ONLY a JSON object: {{\"items\": [<{len(actions)} strings in the same order>]}}\n\n"
        + json.dumps(actions, ensure_ascii=False)
    )
    with _timed(f"translate_steps {language}"):
        resp = client().responses.create(
            model=config.SPARK_MODEL,
            input=[{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            reasoning={"effort": "low"},
        )
    items = parse_json(resp.output_text).get("items", [])
    if len(items) != len(actions):
        raise ValueError(f"translation returned {len(items)} items for {len(actions)} steps")
    return [str(x) for x in items]


# ---------- SAM 3.1 ----------

def sam_track(video: Path, phrase: str) -> dict[int, list[dict]]:
    """One noun phrase per call. Returns {frame_idx: [{id, x1, y1, x2, y2, w, h}]}."""
    with _timed(f"sam_track '{phrase}'"):
        stream = client().responses.create(
            model=config.SAM_MODEL,
            input=[{"role": "user", "content": [
                {"type": "input_text", "text": phrase},
                {"type": "input_video", "video_url": _video_url(video)},
            ]}],
            stream=True,
        )
        text = ""
        for event in stream:
            if getattr(event, "type", "") == "response.output_text.done":
                text = event.text
    return parse_frames(text)


last_sam_raw: str = ""  # raw text of the most recent SAM image reply, for debugging


def sam_image(image: Path, phrase: str) -> list[dict]:
    """SAM 3.1 on one still. Returns [{id, x1, y1, x2, y2, w, h}] for every match."""
    global last_sam_raw
    data = "data:image/jpeg;base64," + base64.b64encode(Path(image).read_bytes()).decode()
    with _timed(f"sam_image '{phrase}'"):
        stream = client().responses.create(
            model=config.SAM_MODEL,
            input=[{"role": "user", "content": [
                {"type": "input_text", "text": phrase},
                {"type": "input_image", "image_url": data},
            ]}],
            stream=True,
        )
        text, deltas, types = "", [], []
        for event in stream:
            etype = getattr(event, "type", "")
            types.append(etype)
            if etype == "response.output_text.delta":
                deltas.append(getattr(event, "delta", ""))
            elif etype == "response.output_text.done":
                text = event.text
            elif etype == "response.completed" and not text:
                text = getattr(event.response, "output_text", "") or ""
        text = text or "".join(deltas)
    last_sam_raw = f"EVENT TYPES: {sorted(set(types))}\n\nTEXT ({len(text)} chars):\n{text[:3000]}"
    return parse_frames(text).get(0, [])


# ---------- Muse Voice Transcribe ----------

_SPEAKER_TAG = re.compile(r"<\|[^|]*\|>")


def transcribe(wav: Path, mode: str = "ENDPOINTING") -> dict:
    """WAV mono 16-bit 16/24 kHz, <=10 min. Returns {"text", "turns": [{start_ms, end_ms, text}]}."""
    req = {"mode": mode, "model": config.ASR_MODEL, "audioEncoding": "WAV"}
    with _timed("transcribe"), Path(wav).open("rb") as audio:
        r = requests.post(
            f"{config.META_BASE_URL}/asr/transcribe",
            params={"sessionId": f"sf-{uuid.uuid4().hex[:10]}"},
            headers={"Authorization": f"Bearer {config.MODEL_API_KEY}"},
            files={"request": (None, json.dumps(req), "application/json"),
                   "audio": (Path(wav).name, audio, "audio/wav")},
            timeout=config.REQUEST_TIMEOUT_S,
        )
    r.raise_for_status()
    body = r.json()
    clean = lambda s: _SPEAKER_TAG.sub("", s or "").strip()  # noqa: E731
    return {
        "text": clean(body.get("transcript")),
        "turns": [{"start_ms": t.get("startMs"), "end_ms": t.get("endMs"), "text": clean(t.get("transcript"))}
                  for t in body.get("turns", [])],
    }


def turns_as_text(turns: list[dict]) -> str:
    return "\n".join(f"[{t['start_ms'] / 1000:.1f}-{t['end_ms'] / 1000:.1f}s] {t['text']}" for t in turns)
