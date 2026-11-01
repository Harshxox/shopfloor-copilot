"""ffmpeg helpers. Every uploaded video is normalised so all Meta APIs accept it."""
import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("media")


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:  # fallback: pip install imageio-ffmpeg
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as e:
        raise RuntimeError("ffmpeg not found. Install it or `pip install imageio-ffmpeg`.") from e


def _run(args: list[str]) -> None:
    cmd = [_ffmpeg(), "-y", "-loglevel", "error", *args]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {res.stderr.strip()[:500]}")


def normalize_video(src: Path, dst: Path, fps: int = 10, max_height: int = 720) -> Path:
    """H.264 MP4, <=720p, 10 fps, small — fits as base64 for Spark and SAM (worked at 7.3 MB / 70 s)."""
    _run(["-i", str(src), "-vf", f"scale=-2:'min({max_height},ih)',fps={fps}",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
          "-c:a", "aac", "-b:a", "48k", "-movflags", "+faststart", str(dst)])
    return dst


def extract_wav(src: Path, dst: Path) -> Path:
    """Mono 16-bit 16 kHz WAV for Muse Voice Transcribe."""
    _run(["-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(dst)])
    return dst


def has_audio(src: Path) -> bool:
    probe = shutil.which("ffprobe")
    if not probe:
        return True  # assume yes; transcription will just return empty
    res = subprocess.run([probe, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                          "-of", "csv=p=0", str(src)], capture_output=True, text=True)
    return bool(res.stdout.strip())


def cut_clip(src: Path, dst: Path, start: float, end: float) -> Path:
    _run(["-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(src),
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-c:a", "aac", str(dst)])
    return dst


def keyframe(src: Path, dst: Path, at_sec: float) -> Path:
    _run(["-ss", f"{max(at_sec, 0):.2f}", "-i", str(src), "-frames:v", "1", "-q:v", "3", str(dst)])
    return dst
