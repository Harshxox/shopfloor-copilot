"""Package one SOP as the built-in demo for the deployed app.

Run from backend\\ :   python scripts\\export_seed.py --sop 3
Writes backend\\seed\\ (sop.json, video.mp4, step_N.jpg) — commit it so the deploy includes it.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import config  # noqa: E402
from app.db import init_db  # noqa: E402
from app.services.seed import export_sop  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--sop", type=int, required=True)
a = ap.parse_args()
init_db()
out = export_sop(a.sop, config.SEED_DIR)
size = sum(f.stat().st_size for f in out.iterdir()) / 1e6
print(f"Exported SOP {a.sop} to {out} ({size:.1f} MB):")
for f in sorted(out.iterdir()):
    print(f"  {f.name}")
