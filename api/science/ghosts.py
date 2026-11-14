"""Ghosts: where each catalogued star should be on each SPHEREx epoch.

Gaia DR3 for ordinary stars; CatWISE2020 adds infrared-only objects (cold brown dwarfs
like WISE 0855 that Gaia can't see). Where both have a source, Gaia wins (better motions).

A source sitting on its ghost is a known star. A source with no ghost nearby is
worth a second look ("candidate for review", never "discovery").
"""

from __future__ import annotations

import warnings
from typing import Any

import astropy.units as u
import numpy as np
from astropy.coordinates import Distance, SkyCoord
from astropy.time import Time

from api.imaging.cutouts import query_frames
from api.imaging.pipeline import split_epochs
from api.science.catalogs import CATWISE_EPOCH_MJD, catwise_cached, gaia_cached

GAIA_EPOCH = Time(2016.0, format="jyear")
CATWISE_EPOCH = Time(CATWISE_EPOCH_MJD, format="mjd")
SAME_SOURCE_ARCSEC = 3.0  # CatWISE source this close to a Gaia star is that star
BRIGHT_G = 10.0  # around stars this bright CatWISE fits halo blobs with fake fast motions
HALO_ARCSEC = 120.0  # (Barnard's star field: a dozen "9 arcsec/yr" sources within 80")
FRAGMENT_ARCSEC = 30.0  # fast movers get split into pieces along their track
FRAGMENT_PM = 1000.0  # mas/yr: pieces of one object share its motion


def clean_catwise(cw: list[dict], gaia: list[dict]) -> list[dict]:
    """Drop CatWISE entries that are Gaia stars, sit in a bright star's halo, or are
    fragments of a brighter CatWISE source. Compared at the CatWISE epoch."""
    if not cw:
        return []
    c0 = np.array([[s["ra"], s["dec"]] for s in cw])
    cosd = np.cos(np.radians(c0[:, 1].mean()))
    keep = np.ones(len(cw), bool)
    if gaia:
        g0 = propagate(gaia, np.array([CATWISE_EPOCH_MJD]))[:, 0]
        sep = 3600 * np.hypot(
            (c0[:, None, 0] - g0[None, :, 0]) * cosd, c0[:, None, 1] - g0[None, :, 1]
        )
        bright = np.array([(g["g_mag"] or 99) < BRIGHT_G for g in gaia])
        keep &= sep.min(axis=1) > SAME_SOURCE_ARCSEC
        if bright.any():
            keep &= ~(sep[:, bright] < HALO_ARCSEC).any(axis=1)
    out: list[dict] = []
    for s, k in zip(cw, keep, strict=True):  # cw is sorted bright first
        if not k:
            continue
        pm = np.array([s["pmra"] or 0.0, s["pmdec"] or 0.0])
        dup = any(
            3600 * np.hypot((s["ra"] - o["ra"]) * cosd, s["dec"] - o["dec"]) < FRAGMENT_ARCSEC
            and np.hypot(*(pm - [o["pmra"] or 0.0, o["pmdec"] or 0.0])) < FRAGMENT_PM
            and np.hypot(*pm) > FRAGMENT_PM
            for o in out
        )
        if not dup:
            out.append(s)
    return out


def propagate(stars: list[dict], mjds: np.ndarray, epoch: Time = GAIA_EPOCH) -> np.ndarray:
    """(n_stars, n_times, 2) array of RA/Dec at each date. Stars without PM stay put."""
    ra = np.array([s["ra"] for s in stars])
    dec = np.array([s["dec"] for s in stars])
    pmra = np.array([s["pmra"] or 0.0 for s in stars])
    pmdec = np.array([s["pmdec"] or 0.0 for s in stars])
    plx = np.array([s["parallax"] if (s["parallax"] or 0) > 0.05 else 0.05 for s in stars])
    c = SkyCoord(
        ra=ra * u.deg,
        dec=dec * u.deg,
        pm_ra_cosdec=pmra * u.mas / u.yr,
        pm_dec=pmdec * u.mas / u.yr,
        distance=Distance(parallax=plx * u.mas),
        radial_velocity=0 * u.km / u.s,
        obstime=epoch,
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
        {
            "epoch": int(e),
            "mjd": round(float(mjd[ep == e].mean()), 4),
            "n_frames": int((ep == e).sum()),
        }
        for e in np.unique(ep)
    ]
    radius = fov * 0.75  # covers the square field's corners plus a fast mover's drift
    mjds = np.array([e["mjd"] for e in epochs])
    gaia = gaia_cached(ra, dec, radius)
    gpos = propagate(gaia, mjds) if gaia else np.empty((0, len(mjds), 2))
    try:
        cw = catwise_cached(ra, dec, radius)
    except Exception:  # IRSA busy: Gaia ghosts alone are still useful
        cw = []
    cw = clean_catwise(cw, gaia)
    cpos = propagate(cw, mjds, CATWISE_EPOCH) if cw else np.empty((0, len(mjds), 2))
    half = fov / 2
    out = []
    for cat, stars, pos in (("gaia", gaia, gpos), ("catwise", cw, cpos)):
        for s, p in zip(stars, pos, strict=True):
            ghosts = []
            for e, (gra, gdec) in zip(epochs, p, strict=True):
                dx = (gra - ra) * np.cos(np.radians(dec))
                if abs(dx) <= half and abs(gdec - dec) <= half:
                    ghosts.append(
                        {
                            "epoch": e["epoch"],
                            "ra": round(float(gra), 6),
                            "dec": round(float(gdec), 6),
                        }
                    )
            if ghosts:
                pm = np.hypot(s["pmra"] or 0, s["pmdec"] or 0)
                out.append(
                    {
                        "source_id": s["source_id"],
                        "catalog": cat,
                        "g_mag": s.get("g_mag"),
                        "w2_mag": s.get("w2_mag"),
                        "pm_mas_yr": round(float(pm), 1),
                        "parallax_mas": s["parallax"],
                        "positions": ghosts,
                    }
                )
    out.sort(key=lambda s: -s["pm_mas_yr"])
    return {"target": {"ra": ra, "dec": dec, "fov": fov}, "epochs": epochs, "stars": out}
