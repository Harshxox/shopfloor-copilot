"""ShopFloor Copilot API (+ the built React app in production)."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .db import init_db
from .routers import report, runs, sops
from .services import media, seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    seed.import_if_empty()  # a fresh deploy starts with the demo SOP ready to check against
    yield


app = FastAPI(title="ShopFloor Copilot", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ffmpeg_ok() -> bool:
    try:
        media._ffmpeg()
        return True
    except RuntimeError:
        return False


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "meta_key_set": bool(config.MODEL_API_KEY),
        "ffmpeg": _ffmpeg_ok(),
        "models": {"spark": config.SPARK_MODEL, "sam": config.SAM_MODEL, "asr": config.ASR_MODEL},
    }


app.include_router(sops.router, prefix="/api/sops", tags=["sops"])
app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
app.include_router(report.router, prefix="/api/report", tags=["report"])
app.mount("/media", StaticFiles(directory=config.DATA_DIR), name="media")

# Production: serve the built React app from the same origin (one URL, one HTTPS cert).
DIST = Path(config.FRONTEND_DIST)
if (DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith(("api/", "media/")):
            raise HTTPException(404)
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
