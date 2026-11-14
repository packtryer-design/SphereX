"""Blink102 API. Shared by Person A (imaging) and Person C (science)."""

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.imaging.config import CACHE_DIR
from api.imaging.pipeline import build_frames
from api.science.asteroids import build_asteroids
from api.science.features import load_features
from api.science.ghosts import build_ghosts
from api.science.spectrum import build_spectrum, load_targets

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


@app.get("/api/spectrum")
def spectrum(
    ra: float = Query(ge=0, lt=360),
    dec: float = Query(ge=-90, le=90),
    target: str | None = Query(None, pattern="^[a-z0-9-]{1,40}$"),
) -> dict[str, Any]:
    """Flux vs wavelength at (ra, dec), one point per frame, plus binned + molecule bands."""
    try:
        return build_spectrum(ra, dec, target)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e


@app.get("/api/ghosts")
def ghosts(
    ra: float = Query(ge=0, lt=360),
    dec: float = Query(ge=-90, le=90),
    fov: float = Query(0.1, ge=0.02, le=0.5),
) -> dict[str, Any]:
    """Gaia DR3 stars moved to each SPHEREx epoch's date."""
    try:
        return build_ghosts(ra, dec, fov)
    except Exception as e:  # Gaia archive or IRSA down
        raise HTTPException(503, f"ghosts unavailable: {e}") from e


@app.get("/api/asteroids")
def asteroids(
    ra: float = Query(ge=0, lt=360),
    dec: float = Query(ge=-90, le=90),
    fov: float = Query(0.1, ge=0.02, le=0.5),
) -> dict[str, Any]:
    """Known asteroids/comets (SkyBoT) in the field at each frame time."""
    try:
        return build_asteroids(ra, dec, fov)
    except Exception as e:  # SkyBoT or IRSA down
        raise HTTPException(503, f"asteroids unavailable: {e}") from e


@app.get("/api/targets")
def targets() -> dict[str, Any]:
    """Demo targets with 2026 positions and the feature profile each uses."""
    feats = load_features()["targets"]
    return {"targets": [t | {"profile": feats.get(t["id"])} for t in load_targets().values()]}
