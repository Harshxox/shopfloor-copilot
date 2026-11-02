"""Simple in-memory rate limits for endpoints that spend Meta Model API credits."""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from . import config

_lock = threading.Lock()
_per_ip: dict[str, deque] = defaultdict(deque)
_daily: deque = deque()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")


def meta_budget(request: Request) -> None:
    """FastAPI dependency: 429 if this visitor or the whole deploy is over its Meta-call budget."""
    now = time.time()
    ip = _client_ip(request)
    with _lock:
        q = _per_ip[ip]
        while q and now - q[0] > 3600:
            q.popleft()
        while _daily and now - _daily[0] > 86400:
            _daily.popleft()
        if len(_daily) >= config.RATE_DAILY_CAP:
            raise HTTPException(429, "Daily demo limit reached — please try again tomorrow.")
        if len(q) >= config.RATE_PER_IP_HOUR:
            raise HTTPException(429, "Too many checks from this device in the last hour — please wait a bit.")
        q.append(now)
        _daily.append(now)


def reset() -> None:
    with _lock:
        _per_ip.clear()
        _daily.clear()
