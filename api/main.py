"""Blink API. Shared by Person A (imaging) and Person C (science).

Also serves the front end from web/, so `make serve` runs the whole app on one port.
"""

from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.imaging.config import CACHE_DIR
from api.imaging.pipeline import build_frames
from api.imaging.visits import list_visits
from api.resolve import resolve
from api.science.spectrum import build_spectrum

WEB_DIR = Path(__file__).resolve().parents[1] / "web"

app = FastAPI(title="Blink")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])  # public read-only
CACHE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/cache", StaticFiles(directory=CACHE_DIR), name="cache")


@app.get("/api/visits")
def visits(
    ra: float = Query(ge=0, lt=360),
    dec: float = Query(ge=-90, le=90),
) -> dict[str, Any]:
    """Real SPHEREx visit dates for a position. Fast: no image downloads."""
    try:
        return list_visits(ra, dec)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e


@app.get("/api/frames")
def frames(
    ra: float = Query(ge=0, lt=360),
    dec: float = Query(ge=-90, le=90),
    fov: float = Query(0.1, ge=0.02, le=0.5),
    mode: str = Query("single", pattern="^(single|epoch|rgb|diff)$"),
    detector: str = Query("all", pattern="^(all|[1-6])$"),
    ref: int | None = Query(None, ge=1, description="diff only: epoch to compare against"),
) -> dict[str, Any]:
    try:
        return build_frames(ra, dec, fov, mode, detector, ref)
    except RuntimeError as e:  # IRSA down and nothing cached for this position
        raise HTTPException(503, str(e)) from e


@app.get("/api/spectrum")
def spectrum(
    ra: float = Query(ge=0, lt=360),
    dec: float = Query(ge=-90, le=90),
    field_ra: float | None = Query(None, ge=0, lt=360),
    field_dec: float | None = Query(None, ge=-90, le=90),
    fov: float = Query(0.1, ge=0.02, le=0.5),
) -> dict[str, Any]:
    """Spectrum at (ra, dec). Pass the open field's centre and fov to reuse its cutouts."""
    try:
        return build_spectrum(
            ra,
            dec,
            ra if field_ra is None else field_ra,
            dec if field_dec is None else field_dec,
            fov,
        )
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e


@app.get("/api/resolve")
def resolve_name(name: str = Query(min_length=2, max_length=80)) -> dict[str, Any]:
    try:
        found = resolve(name)
    except httpx.HTTPError as e:
        raise HTTPException(503, f"Name lookup unavailable: {e}") from e
    if not found:
        raise HTTPException(404, f"No object called '{name}'")
    return found


# Last, so /api and /cache win.
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
