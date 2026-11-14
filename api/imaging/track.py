"""Follow a Solar System body through SPHEREx frames: fixed sky grid, body drifts across it.

Positions come from NASA JPL Horizons. Each frame carries where the body *should* be, so the
viewer can mark it and scripts/check_track.py can measure how well the images agree.
"""

import json
import warnings
from typing import Any

import numpy as np
from astropy.coordinates import SkyCoord
from astroquery.jplhorizons import Horizons

from api.imaging.config import CACHE_DIR
from api.imaging.cutouts import fetch_cutouts
from api.imaging.pipeline import (
    RESPONSE_VERSION,
    _save_png,
    _wavelength_at,
    align,
    normalize,
    stretch,
    target_grid,
)

# Allowlist, not free text: the id goes to an external service from a public endpoint.
BODIES = {
    "pluto": ("999", None, "Pluto"),
}


def ephemeris(body: str, start: float, stop: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Hourly (mjd, ra, dec). Geocentric: SPHEREx's low-Earth-orbit offset is < 0.01" at Pluto."""
    hid, id_type, _ = BODIES[body]
    eph = Horizons(
        id=hid,
        id_type=id_type,
        location="500",
        epochs={
            "start": f"JD{start + 2400000.5:.4f}",
            "stop": f"JD{stop + 2400000.5:.4f}",
            "step": "1h",
        },
    ).ephemerides()
    return np.array(eph["datetime_jd"]) - 2400000.5, np.array(eph["RA"]), np.array(eph["DEC"])


def build_track(body: str, mjd: float, days: float = 2.0, fov: float = 0.1) -> dict[str, Any]:
    mjd, days, fov = round(mjd, 2), round(days, 2), round(fov, 3)
    key = f"v{RESPONSE_VERSION}_track_{body}_{mjd:.2f}_{days:.2f}_{fov:.3f}"
    cached = CACHE_DIR / "responses" / f"{key}.json"
    if cached.exists():
        return dict(json.loads(cached.read_text()))

    t, ra, dec = ephemeris(body, mjd - days, mjd + days)
    ra = np.degrees(np.unwrap(np.radians(ra)))  # safe interpolation across RA = 0/360
    ra0, dec0 = float(np.interp(mjd, t, ra)) % 360, float(np.interp(mjd, t, dec))
    out_wcs, shape = target_grid(ra0, dec0, fov)

    cuts, failed = fetch_cutouts(ra0, dec0, fov, mjd_range=(mjd - days, mjd + days))
    frames, zs = [], []
    for c in sorted(cuts, key=lambda c: c.mjd):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            a = align(c.img, c.wcs, out_wcs, shape)
        if np.isnan(a).mean() > 0.5:
            continue
        pra, pdec = float(np.interp(c.mjd, t, ra)) % 360, float(np.interp(c.mjd, t, dec))
        x, y = out_wcs.world_to_pixel(SkyCoord(pra, pdec, unit="deg"))
        zs.append(normalize(a))
        frames.append(
            {
                "mjd": round(c.mjd, 4),
                "detector": c.detector,
                "wavelength_um": _wavelength_at(c, pra, pdec),
                # pixel origin bottom-left (FITS); the PNG is flipped, so y_png = n - 1 - y
                "predicted": {
                    "ra": round(pra, 6),
                    "dec": round(pdec, 6),
                    "x": round(float(x), 2),
                    "y": round(float(y), 2),
                },
            }
        )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        vmax = float(np.nanpercentile(np.stack(zs), 99.5)) if zs else 1.0
    for i, (z, f) in enumerate(zip(zs, frames, strict=True)):
        f["png"] = _save_png(stretch(z, -2, vmax), f"png/{key}/{i:03d}.png")

    resp = {
        "body": body,
        "name": BODIES[body][2],
        "target": {"ra": round(ra0, 6), "dec": round(dec0, 6), "fov": fov, "size_px": shape[0]},
        "window": {"mjd_start": mjd - days, "mjd_end": mjd + days},
        "frames": frames,
        "source": "Positions: NASA JPL Horizons (geocentric). Images: NASA/IPAC IRSA SPHEREx.",
    }
    if not failed:  # a partial result must not be frozen in the cache
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(resp))
    return resp
