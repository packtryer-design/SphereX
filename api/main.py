"""Blink102 API. Shared by Person A (imaging) and Person C (science)."""

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.imaging.config import CACHE_DIR
from api.imaging.pipeline import build_frames

app = FastAPI(title="Blink102")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])  # public read-only
CACHE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/cache", StaticFiles(directory=CACHE_DIR), name="cache")


@app.get("/api/frames")
def frames(
    ra: float = Query(ge=0, lt=360),
    dec: float = Query(ge=-90, le=90),
    fov: float = Query(0.1, ge=0.02, le=0.5),
    mode: str = Query("single", pattern="^(single|epoch|rgb|diff)$"),
    detector: str = Query("all", pattern="^(all|[1-6])$"),
) -> dict[str, Any]:
    try:
        return build_frames(ra, dec, fov, mode, detector)
    except RuntimeError as e:  # IRSA down and nothing cached for this position
        raise HTTPException(503, str(e)) from e
