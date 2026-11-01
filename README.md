# ShopFloor Copilot

An expert does a job once wearing a camera; every new worker then gets each step checked and corrected out loud in their own language. Built on Meta's Muse Spark, SAM 3.1 and Muse Voice Transcribe for the Meta Global AI Developer Hackathon (27 Oct – 4 Nov 2026).

## Run locally

Needs Python 3.10+, Node 20, ffmpeg, and a Meta Model API key in `.env` (copy `.env.example`).

**Backend** (terminal 1):
```
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Check: http://localhost:8000/api/health and API docs at http://localhost:8000/docs

**Frontend** (terminal 2):
```
cd frontend
npm install
npm run dev
```
Open http://localhost:5173 — the badge top-right should say **Backend ready**.

**Or with Docker:** `docker compose up --build`

**Tests:** `cd backend && python -m pytest -q`

## Layout
```
backend/app/
  main.py               FastAPI app, /api/health
  config.py             settings from .env
  models.py             SOP, Step, CheckRun, Event tables
  db.py                 SQLite via SQLModel
  routers/sops.py       Teach mode API
  routers/runs.py       Check mode API
  services/meta_client.py  every Meta Model API call (Spark, SAM 3.1, Transcribe)
  services/media.py     ffmpeg: normalise, extract audio, cut clips, keyframes
  services/sam_parse.py SAM 3.1 output parser
frontend/src/           React app: Teach, Check, Report
spikes/                 Phase 1 API experiments (see SPIKES.md)
```
