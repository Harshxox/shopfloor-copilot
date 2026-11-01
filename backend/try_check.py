"""Try Check mode on a real clip through the running API (uvicorn must be on :8000).

Example (from backend\\):
  python try_check.py --sop 2 --lang kn --clip ..\\spikes\\media\\step.mp4 --step 3
  python try_check.py --sop 2 --lang kn --clip ..\\spikes\\media\\step.mp4 --step 5
"""
import argparse
import json
import time

import requests

API = "http://localhost:8000/api"

ap = argparse.ArgumentParser()
ap.add_argument("--sop", type=int, required=True)
ap.add_argument("--clip", required=True)
ap.add_argument("--step", type=int, required=True, help="SOP step number the clip should be checked against")
ap.add_argument("--lang", default="en", choices=["en", "kn", "hi"])
ap.add_argument("--no-sam", action="store_true")
a = ap.parse_args()

r = requests.post(f"{API}/runs", json={"sop_id": a.sop, "worker_language": a.lang})
r.raise_for_status()
run = r.json()
run_id = run["run"]["id"]
print(f"Run {run_id} started. Worker hears: {run['say']}\n")
print("Steps in worker language:")
for k, v in run["step_texts"].items():
    print(f"  {k}. {v}")

print(f"\nChecking clip against step {a.step} ... (~20-40 s)")
t0 = time.time()
with open(a.clip, "rb") as f:
    r = requests.post(f"{API}/runs/{run_id}/check",
                      files={"clip": (a.clip.split("\\")[-1].split("/")[-1], f, "video/mp4")},
                      data={"step_idx": a.step, "use_sam": str(not a.no_sam).lower()}, timeout=300)
if not r.ok:
    print("ERROR", r.status_code, r.text)
    raise SystemExit(1)
res = r.json()
ev = res["event"]
print(f"Done in {time.time() - t0:.1f} s   stages: {res.get('timings')}\n")
print(f"VERDICT : {ev['kind'].upper()} {('(' + ev['deviation_type'] + ')') if ev['deviation_type'] else ''}")
if ev["observed_step_id"]:
    print(f"Clip actually shows step: {ev['observed_step_id']}")
print(f"Evidence: {ev['evidence'] or ev['reason']}")
print(f"WORKER HEARS: {res['say']}")
print(f"Clip: http://localhost:8000/media/{ev['clip_path']}")
if res.get("overlay_pending"):
    print(f"SAM hands overlay is being built in the background; it appears in ~20 s at "
          f"http://localhost:8000/media/{ev['clip_path'].replace('.mp4', '_hands.mp4')}")
print(f"\nBlind observation:\n{ev['observation'][:800]}")
