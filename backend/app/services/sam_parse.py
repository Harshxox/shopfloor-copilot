"""Parse SAM 3.1 special-token output into per-frame boxes.

Wire format (one video): <Nf> = frame N, then per object:
  <obj_id><|box;x1=..;y1=..;x2=..;y2=..;w=W;h=H|><|mask;x=..;y=..;data=...|>
Object IDs stay the same across frames (that's the tracking).
Masks are a compressed payload ('~' = lossless); we use boxes in Python and
decode masks in the browser with Meta's @meta-sam/parser later.
"""
import json
import re
from pathlib import Path

FRAME_RE = re.compile(r"<(\d+)f>")
BOX_RE = re.compile(r"(\d+)<\|box;([^|]*)\|>")


def text_from_jsonl(path: Path) -> str:
    """Get the full model text from a saved stream (.jsonl of events)."""
    with path.open() as f:
        for line in f:
            if '"response.output_text.done"' in line:
                return json.loads(line)["text"]
    raise ValueError("no response.output_text.done event in file")


def parse_frames(text: str) -> dict[int, list[dict]]:
    """Return {frame_index: [{"id", "x1", "y1", "x2", "y2", "w", "h"}, ...]}."""
    frames: dict[int, list[dict]] = {}
    if not FRAME_RE.search(text):  # a single image has no <Nf> frame markers
        text = "<0f>" + text
    parts = FRAME_RE.split(text)  # ['', '0', '<frame 0 body>', '1', '<frame 1 body>', ...]
    for i in range(1, len(parts) - 1, 2):
        idx, body = int(parts[i]), parts[i + 1]
        objs = []
        for obj_id, fields in BOX_RE.findall(body):
            kv = dict(f.split("=") for f in fields.split(";"))
            objs.append({"id": int(obj_id), **{k: int(v) for k, v in kv.items()}})
        frames[idx] = objs
    return frames


def summary(frames: dict[int, list[dict]]) -> dict:
    ids: dict[int, int] = {}
    for objs in frames.values():
        for o in objs:
            ids[o["id"]] = ids.get(o["id"], 0) + 1
    return {"n_frames": len(frames), "frames_per_object_id": ids}
