"""Spike 1.3 — Can SAM 3.1 track hands/parts in our clip, and what does its output look like?

SAM 3.1 takes ONE short noun phrase per request and streams back boxes + masks per object.
This spike dumps every streamed event so we learn the exact format before writing the overlay code.

Run:  python spikes/sam_video.py [clip.mp4] "hand"
      python spikes/sam_video.py [clip.mp4] "screwdriver"
Pass: out/sam_<prompt>.jsonl has box/mask records spread across frames, with stable object IDs.
"""
import json
import sys
from collections import Counter
from pathlib import Path

from common import MEDIA, OUT, SAM_MODEL, client, save, timed, video_data_url

clip = Path(sys.argv[1]) if len(sys.argv) > 1 else MEDIA / "expert.mp4"
prompt = sys.argv[2] if len(sys.argv) > 2 else "hand"
slug = prompt.replace(" ", "_")

log = {"model": SAM_MODEL, "clip": clip.name, "prompt": prompt}
event_types = Counter()
out_path = OUT / f"sam_{slug}.jsonl"

with timed("sam_latency_s", log), out_path.open("w") as f:
    stream = client.responses.create(
        model=SAM_MODEL,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_video", "video_url": video_data_url(clip)},
            ],
        }],
        stream=True,
    )
    for event in stream:
        data = event.model_dump() if hasattr(event, "model_dump") else dict(event)
        event_types[data.get("type", "unknown")] += 1
        f.write(json.dumps(data, default=str) + "\n")

log["event_types"] = dict(event_types)
log["n_events"] = sum(event_types.values())
print(f"[saved] {out_path}")
print("Event types:", dict(event_types))
print("Next: open the .jsonl, find where boxes/masks/frame index/object id live, and paste one record to Claude.")
save(f"log_sam_{slug}.json", log)
