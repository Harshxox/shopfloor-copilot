"""Spike 1.2 — Can Muse Spark watch an assembly clip and return a step list as JSON?

Run:  python spikes/spark_video.py [path/to/clip.mp4]
Pass: out/spark_steps.json has sensible steps with start/end times.
"""
import json
import sys
from pathlib import Path

from common import MEDIA, SPARK_MODEL, client, save, timed, video_data_url

clip = Path(sys.argv[1]) if len(sys.argv) > 1 else MEDIA / "expert.mp4"

SCHEMA = {
    "type": "object",
    "properties": {
        "task_name": {"type": "string"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "action": {"type": "string"},
                    "parts": {"type": "array", "items": {"type": "string"}},
                    "tools": {"type": "array", "items": {"type": "string"}},
                    "expected_end_state": {"type": "string"},
                    "critical": {"type": "boolean"},
                    "start_sec": {"type": "number"},
                    "end_sec": {"type": "number"},
                },
                "required": ["id", "action", "parts", "tools", "expected_end_state",
                             "critical", "start_sec", "end_sec"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["task_name", "steps"],
    "additionalProperties": False,
}

PROMPT = (
    "You are an industrial engineer writing a standard operating procedure (SOP).\n"
    "Watch this whole video from start to end (and listen to any narration).\n"
    "List EVERY physical step the person performs, in order — typically 3 to 12 steps. "
    "Do not return an empty list.\n"
    "For each step give: id, action (imperative, e.g. 'Remove the top screw'), parts, tools, "
    "expected_end_state (what it looks like when done), critical (true if skipping it causes a defect "
    "or safety risk), start_sec and end_sec.\n"
    "Return ONLY a JSON object, no markdown fences, in exactly this shape:\n"
    + json.dumps({
        "task_name": "string",
        "steps": [{"id": 1, "action": "string", "parts": ["string"], "tools": ["string"],
                   "expected_end_state": "string", "critical": True, "start_sec": 0.0, "end_sec": 5.0}],
    })
)


def parse_json(text: str):
    """Pull the first {...} JSON object out of the model's text."""
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


log = {"model": SPARK_MODEL, "clip": clip.name, "clip_mb": round(clip.stat().st_size / 1e6, 2)}
data_url = video_data_url(clip)
sop, raw = None, ""

for attempt in (1, 2):
    with timed(f"spark_video_latency_s_try{attempt}", log):
        resp = client.responses.create(
            model=SPARK_MODEL,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_video", "video_url": data_url},
                    {"type": "input_text", "text": PROMPT},
                ],
            }],
            reasoning={"effort": "medium"},
            max_output_tokens=8000,
        )
    raw = resp.output_text
    if getattr(resp, "usage", None):
        log[f"usage_try{attempt}"] = resp.usage.model_dump()
    try:
        sop = parse_json(raw)
        if sop.get("steps"):
            break
        print(f"Attempt {attempt}: empty steps, retrying...")
    except (json.JSONDecodeError, ValueError):
        print(f"Attempt {attempt}: could not parse JSON, retrying...")

save("spark_steps_raw.txt", raw)
if sop and sop.get("steps"):
    log["json_valid"] = True
    log["n_steps"] = len(sop["steps"])
    save("spark_steps.json", sop)
    print(f"\nTask: {sop.get('task_name')}")
    for s in sop["steps"]:
        flag = " [CRITICAL]" if s.get("critical") else ""
        print(f"{s['id']:>2}. {s.get('start_sec', 0):>5.1f}-{s.get('end_sec', 0):<5.1f}s  {s['action']}{flag}")
else:
    log["json_valid"] = False
    print("No steps after 2 tries — open out/spark_steps_raw.txt and paste it to Claude.")

save("log_spark_video.json", log)
