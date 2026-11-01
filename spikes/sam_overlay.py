"""Draw SAM 3.1 tracks (boxes + stable IDs) onto the video so we can SEE the tracking.

Run:  python spikes/sam_overlay.py spikes/media/expert.mp4 spikes/out/sam_hand.jsonl hand
Out:  spikes/out/overlay_hand.mp4  — open it and check the boxes follow your hands.
"""
import sys
from pathlib import Path

import cv2

from sam_parse import parse_frames, summary, text_from_jsonl

video = Path(sys.argv[1])
jsonl = Path(sys.argv[2])
label = sys.argv[3] if len(sys.argv) > 3 else "obj"
out_path = jsonl.parent / f"overlay_{label}.mp4"

frames = parse_frames(text_from_jsonl(jsonl))
print(summary(frames))

cap = cv2.VideoCapture(str(video))
fps = cap.get(cv2.CAP_PROP_FPS) or 10
n_video = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
duration = n_video / fps
sam_fps = len(frames) / duration  # SAM may sample at a different rate than the file
print(f"video {W}x{H} @ {fps:.1f} fps, {duration:.1f} s | SAM frames {len(frames)} (~{sam_fps:.1f} fps)")

COLORS = [(0, 200, 255), (255, 120, 0), (0, 220, 0), (200, 0, 200), (0, 0, 255), (255, 255, 0)]
writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))

i = 0
while True:
    ok, img = cap.read()
    if not ok:
        break
    sam_idx = min(int(round(i / fps * sam_fps)), len(frames) - 1)
    for o in frames.get(sam_idx, []):
        sx, sy = W / o["w"], H / o["h"]  # SAM boxes are in its own w/h space
        p1 = (int(o["x1"] * sx), int(o["y1"] * sy))
        p2 = (int(o["x2"] * sx), int(o["y2"] * sy))
        c = COLORS[o["id"] % len(COLORS)]
        cv2.rectangle(img, p1, p2, c, 3)
        cv2.putText(img, f"{label} #{o['id']}", (p1[0] + 4, max(p1[1] + 22, 22)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, c, 2)
    cv2.putText(img, f"t={i / fps:5.1f}s  SAM frame {sam_idx}", (10, H - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    writer.write(img)
    i += 1

cap.release()
writer.release()
print(f"[saved] {out_path}")
