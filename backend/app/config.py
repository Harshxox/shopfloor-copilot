"""App settings, read once from environment / .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]  # repo root
load_dotenv(ROOT / ".env")

MODEL_API_KEY = os.environ.get("MODEL_API_KEY", "")
META_BASE_URL = os.environ.get("META_BASE_URL", "https://api.meta.ai/v1")
SPARK_MODEL = os.environ.get("SPARK_MODEL", "muse-spark-1.2")
SAM_MODEL = os.environ.get("SAM_MODEL", "sam-3.1")
ASR_MODEL = os.environ.get("ASR_MODEL", "muse-voice-transcribe-1.0")

DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_URL = os.environ.get("DB_URL", f"sqlite:///{DATA_DIR / 'shopfloor.db'}")

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
REQUEST_TIMEOUT_S = float(os.environ.get("REQUEST_TIMEOUT_S", "180"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "2"))
