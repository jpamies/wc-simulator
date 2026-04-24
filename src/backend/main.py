"""WC Simulator 2026 — Main FastAPI application."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.backend.config import CORS_ORIGINS
from src.backend.database import init_db
from src.backend.services.data_import import import_all
from src.backend.services.tournament_engine import recalculate_group_standings

from src.backend.routes.tournament import router as tournament_router
from src.backend.routes.data import router as data_router
from src.backend.routes.matches import router as matches_router
from src.backend.routes.simulation import router as simulation_router
from src.backend.routes.squads import router as squads_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await import_all()
    await recalculate_group_standings()
    yield


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
        if not path.startswith("/api/"):
            if path.endswith(".html") or path == "/" or "." not in path.split("/")[-1]:
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            else:
                response.headers["Cache-Control"] = "public, max-age=300"
        return response


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
