"""SpotX API. Shared by Person A (imaging) and Person C (science).

Also serves the front end from web/, so `make serve` runs the whole app on one port.
"""

from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.imaging.config import CACHE_DIR
from api.imaging.pipeline import build_frames, seed_cache
from api.imaging.planetx import build_planetx
from api.imaging.track import BODIES, build_track
from api.imaging.visits import list_visits
from api.resolve import resolve
from api.science.asteroids import build_asteroids
from api.science.features import load_features
from api.science.ghosts import build_ghosts
from api.science.spectrum import build_spectrum, load_targets
from api.science.surface import build_surface_spectrum

WEB_DIR = Path(__file__).resolve().parents[1] / "web"

app = FastAPI(title="SpotX")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])  # public read-only
CACHE_DIR.mkdir(parents=True, exist_ok=True)
seed_cache()
app.mount("/cache", StaticFiles(directory=CACHE_DIR), name="cache")


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Cheap check the front end uses to find a live API (see scripts/host.py)."""
    return {"ok": True, "name": "SpotX"}


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


@app.get("/api/track")
def track(
    body: str = Query("pluto", pattern=f"^({'|'.join(BODIES)})$"),
    mjd: float = Query(60956.0, ge=60700, le=70000),  # SPHEREx data starts mid-2025
    days: float = Query(2.0, gt=0, le=5),
    fov: float = Query(0.1, ge=0.02, le=0.5),
) -> dict[str, Any]:
    """A Solar System body followed through SPHEREx frames, with JPL Horizons positions."""
    try:
        return build_track(body, mjd, days, fov)
    except Exception as e:  # IRSA or JPL Horizons down, nothing cached
        raise HTTPException(503, f"tracking unavailable: {e}") from e


@app.get("/api/planetx")
def planetx(
    body: str = Query("pluto", pattern=f"^({'|'.join(BODIES)})$"),
    mjd: float = Query(60956.0, ge=60700, le=70000),
    days: float = Query(2.0, gt=0, le=5),
) -> dict[str, Any]:
    """Shift-and-stack planet search: finds the tracked body blind, then a planted Planet X."""
    try:
        return build_planetx(body, round(mjd, 2), round(days, 2))
    except Exception as e:  # IRSA or JPL Horizons down, nothing cached
        raise HTTPException(503, f"planet search unavailable: {e}") from e


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
    target: str | None = Query(None, pattern="^[a-z0-9-]{1,40}$"),
) -> dict[str, Any]:
    """Point sources: flux vs wavelength at (ra, dec), one point per frame, plus binned +
    molecule bands. Aperture photometry with a sky annulus."""
    try:
        return build_spectrum(ra, dec, target)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e


@app.get("/api/surface-spectrum")
def surface_spectrum(
    ra: float = Query(ge=0, lt=360),
    dec: float = Query(ge=-90, le=90),
    field_ra: float | None = Query(None, ge=0, lt=360),
    field_dec: float | None = Query(None, ge=-90, le=90),
    fov: float = Query(0.1, ge=0.02, le=0.5),
) -> dict[str, Any]:
    """Extended objects (nebulae): surface brightness at (ra, dec), one point per frame.
    Pass the open field's centre and fov to reuse its cutouts."""
    try:
        return build_surface_spectrum(
            ra,
            dec,
            ra if field_ra is None else field_ra,
            dec if field_dec is None else field_dec,
            fov,
        )
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
