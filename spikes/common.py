"""Shared helpers for Phase 1 API spikes."""
import base64
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_URL = "https://api.meta.ai/v1"
API_KEY = os.environ.get("MODEL_API_KEY")
SPARK_MODEL = os.environ.get("SPARK_MODEL", "muse-spark-1.2")  # 1.3 has degraded audio; 1.2 is safe for video+sound
SAM_MODEL = "sam-3.1"
ASR_MODEL = "muse-voice-transcribe-1.0"

ROOT = Path(__file__).resolve().parent
MEDIA = ROOT / "media"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

if not API_KEY:
    raise SystemExit("MODEL_API_KEY missing. Put it in .env (see .env.example).")

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)


def video_data_url(path: Path) -> str:
    """Encode a small MP4 as a base64 data URL (keep clips under ~8 MB)."""
    size_mb = path.stat().st_size / 1e6
    if size_mb > 8:
        print(f"WARNING: {path.name} is {size_mb:.1f} MB; re-encode smaller with prepare_media.sh")
    return "data:video/mp4;base64," + base64.b64encode(path.read_bytes()).decode()


@contextmanager
def timed(label: str, log: dict):
    t0 = time.perf_counter()
    yield
    log[label] = round(time.perf_counter() - t0, 2)
    print(f"[time] {label}: {log[label]} s")


def save(name: str, data) -> Path:
    p = OUT / name
    if isinstance(data, (dict, list)):
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        p.write_text(str(data))
    print(f"[saved] {p}")
    return p
