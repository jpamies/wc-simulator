"""WC Simulator 2026 — Main FastAPI application."""

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.backend.config import CORS_ORIGINS
from src.backend.database import init_db, close_pool
from src.backend.services.data_import import import_all
from src.backend.services.tournament_engine import recalculate_group_standings

from src.backend.routes.tournament import router as tournament_router
from src.backend.routes.data import router as data_router
from src.backend.routes.matches import router as matches_router
from src.backend.routes.simulation import router as simulation_router
from src.backend.routes.squads import router as squads_router

logger = logging.getLogger("wc-simulator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await import_all()
    await recalculate_group_standings()
    yield
    await close_pool()


app = FastAPI(
    title="WC Simulator 2026",
    description="World Cup 2026 match simulator and data API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS.split(",") if CORS_ORIGINS != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        # Log slow API requests (>500ms)
        if path.startswith("/api/"):
            duration = response.headers.get("X-Response-Time")
            if duration:
                ms = float(duration)
                if ms > 500:
                    logger.warning(f"SLOW {request.method} {path} took {ms:.0f}ms")
        if not path.startswith("/api/"):
            if path.endswith(".html") or path == "/" or "." not in path.split("/")[-1]:
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            else:
                response.headers["Cache-Control"] = "public, max-age=300"
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Add X-Response-Time header and log slow API requests."""
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000
        response.headers["X-Response-Time"] = f"{ms:.0f}"
        if request.url.path.startswith("/api/") and ms > 200:
            logger.warning(f"SLOW {request.method} {request.url.path} {ms:.0f}ms")
        return response


app.add_middleware(TimingMiddleware)
app.add_middleware(NoCacheStaticMiddleware)

# ─── API routes under /api/v1 ───
app.include_router(tournament_router, prefix="/api/v1")
app.include_router(data_router, prefix="/api/v1")
app.include_router(matches_router, prefix="/api/v1")
app.include_router(simulation_router, prefix="/api/v1")
app.include_router(squads_router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "app": "wc-simulator-2026"}


# ─── Serve frontend ───
_project_root = Path(__file__).resolve().parent.parent.parent
_frontend_dir = _project_root / "src" / "frontend"
if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
