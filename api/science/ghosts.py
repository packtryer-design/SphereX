"""Gaia ghosts: where Gaia DR3 says each star should be on each SPHEREx epoch.

A source sitting on its ghost is a known star. A source with no ghost nearby is
worth a second look ("candidate for review", never "discovery").
"""

from __future__ import annotations

import json
import warnings
from typing import Any

import astropy.units as u
import numpy as np
from astropy.coordinates import Distance, SkyCoord
from astropy.time import Time

from api.imaging.config import CACHE_DIR
from api.imaging.cutouts import query_frames
from api.imaging.pipeline import split_epochs

GAIA_EPOCH = Time(2016.0, format="jyear")
MAX_STARS = 300
MAG_LIMIT = 17.0  # fainter than this SPHEREx won't see it at 6" pixels


def gaia_cone(ra: float, dec: float, radius_deg: float) -> list[dict]:
    from astroquery.gaia import Gaia

    q = f"""
    SELECT TOP {MAX_STARS} source_id, ra, dec, pmra, pmdec, parallax, phot_g_mean_mag
    FROM gaiadr3.gaia_source
    WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra}, {dec}, {radius_deg}))
      AND phot_g_mean_mag < {MAG_LIMIT}
    ORDER BY phot_g_mean_mag
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tab = Gaia.launch_job(q).get_results()
    rows = []
    for r in tab:
        def f(k):
            v = r[k]
            return None if np.ma.is_masked(v) else float(v)

        rows.append({
            "source_id": str(r["source_id"] if "source_id" in tab.colnames else r["SOURCE_ID"]),
            "ra": f("ra"), "dec": f("dec"), "pmra": f("pmra"), "pmdec": f("pmdec"),
            "parallax": f("parallax"), "g_mag": round(f("phot_g_mean_mag"), 2),
        })
    return rows


def _gaia_cached(ra: float, dec: float, radius: float) -> list[dict]:
    p = CACHE_DIR / "gaia" / f"{ra:.4f}_{dec:+.4f}_{radius:.3f}.json"
    if p.exists():
        return list(json.loads(p.read_text()))
    rows = gaia_cone(ra, dec, radius)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows))
    return rows


def propagate(stars: list[dict], mjds: np.ndarray) -> np.ndarray:
    """(n_stars, n_times, 2) array of RA/Dec at each date. Stars without PM stay put."""
    ra = np.array([s["ra"] for s in stars])
    dec = np.array([s["dec"] for s in stars])
    pmra = np.array([s["pmra"] or 0.0 for s in stars])
    pmdec = np.array([s["pmdec"] or 0.0 for s in stars])
    plx = np.array([s["parallax"] if (s["parallax"] or 0) > 0.05 else 0.05 for s in stars])
    c = SkyCoord(
        ra=ra * u.deg, dec=dec * u.deg,
        pm_ra_cosdec=pmra * u.mas / u.yr, pm_dec=pmdec * u.mas / u.yr,
        distance=Distance(parallax=plx * u.mas),
        radial_velocity=0 * u.km / u.s,
        obstime=GAIA_EPOCH,
    )
    out = np.empty((len(stars), len(mjds), 2))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # ERFA "dubious year" notices
        for j, m in enumerate(mjds):
            moved = c.apply_space_motion(new_obstime=Time(m, format="mjd"))
            out[:, j, 0] = moved.ra.deg
            out[:, j, 1] = moved.dec.deg
    return out


def build_ghosts(ra: float, dec: float, fov: float) -> dict[str, Any]:
    ra, dec, fov = round(ra, 4), round(dec, 4), round(fov, 3)
    frames = query_frames(ra, dec)
    if not frames:
        return {"target": {"ra": ra, "dec": dec, "fov": fov}, "epochs": [], "stars": []}
    mjd = np.array(sorted(f[1] for f in frames))
    ep = split_epochs(mjd)
    epochs = [
        {"epoch": int(e), "mjd": round(float(mjd[ep == e].mean()), 4), "n_frames": int((ep == e).sum())}
        for e in np.unique(ep)
    ]
    radius = fov * 0.75  # covers the square field's corners plus a fast mover's drift
    stars = _gaia_cached(ra, dec, radius)
    pos = propagate(stars, np.array([e["mjd"] for e in epochs])) if stars else np.empty((0, 0, 2))
    half = fov / 2
    out = []
    for s, p in zip(stars, pos, strict=True):
        ghosts = []
        for e, (gra, gdec) in zip(epochs, p, strict=True):
            dx = (gra - ra) * np.cos(np.radians(dec))
            if abs(dx) <= half and abs(gdec - dec) <= half:
                ghosts.append({"epoch": e["epoch"], "ra": round(float(gra), 6), "dec": round(float(gdec), 6)})
        if ghosts:
            pm = np.hypot(s["pmra"] or 0, s["pmdec"] or 0)
            out.append({
                "source_id": s["source_id"], "g_mag": s["g_mag"],
                "pm_mas_yr": round(float(pm), 1), "parallax_mas": s["parallax"],
                "positions": ghosts,
            })
    out.sort(key=lambda s: -s["pm_mas_yr"])
    return {"target": {"ra": ra, "dec": dec, "fov": fov}, "epochs": epochs, "stars": out}
