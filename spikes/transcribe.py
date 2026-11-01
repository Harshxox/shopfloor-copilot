"""Spike 1.4 — Can Muse Voice Transcribe turn the expert's narration into timestamped text?

Input must be WAV, mono, 16-bit PCM, 16 kHz or 24 kHz, max 10 min / 32 MB (prepare_media.sh makes it).
Run:  python spikes/transcribe.py [narration.wav]
Pass: out/transcript.json has turns with timings. Test English first, then Kannada and Hindi.
"""
import json
import sys
import uuid
from pathlib import Path

import requests

from common import API_KEY, ASR_MODEL, BASE_URL, MEDIA, save, timed

wav = Path(sys.argv[1]) if len(sys.argv) > 1 else MEDIA / "expert.wav"
mode = sys.argv[2] if len(sys.argv) > 2 else "ENDPOINTING"  # or DIARIZATION

log = {"model": ASR_MODEL, "file": wav.name, "mode": mode}
request_json = {"mode": mode, "model": ASR_MODEL, "audioEncoding": "WAV"}

with timed("asr_latency_s", log), wav.open("rb") as audio:
    r = requests.post(
        f"{BASE_URL}/asr/transcribe",
        params={"sessionId": f"spike-{uuid.uuid4().hex[:8]}"},
        headers={"Authorization": f"Bearer {API_KEY}"},
        files={
            "request": (None, json.dumps(request_json), "application/json"),
            "audio": (wav.name, audio, "audio/wav"),
        },
        timeout=300,
    )

log["status"] = r.status_code
if r.ok:
    try:
        body = r.json()
    except ValueError:
        body = {"raw_text": r.text}
    save("transcript.json", body)
    print(json.dumps(body, indent=2, ensure_ascii=False)[:2000])
else:
    log["error"] = r.text[:1000]
    print("ERROR", r.status_code, r.text[:1000])
save("log_transcribe.json", log)
