"""Turn SPHEREx cutouts into a spectrum: one flux point per frame.

Each SPHEREx frame sees the target at a single wavelength (the linear variable
filter puts a different wavelength on every row), so stacking every frame that
covers a star gives its whole 0.75-5 um spectrum.
"""

from __future__ import annotations

import json
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from astropy.time import Time

from api.imaging.config import CACHE_DIR, PIXEL_SCALE_ARCSEC
from api.imaging.cutouts import Cutout, fetch_cutouts
from api.imaging.pipeline import split_epochs
from api.science.features import interpret

TARGETS_PATH = Path(__file__).resolve().parents[2] / "data" / "targets.json"
SPEC_FOV = 0.03  # deg; small cutouts, just enough for aperture + sky annulus
AP_R = 2.0  # px aperture radius (PSF FWHM is ~1-2 px)
SKY_R = (4.0, 7.0)  # px sky annulus
PIX_SR = (PIXEL_SCALE_ARCSEC / 206264.806) ** 2
MJY_SR_TO_MJY = PIX_SR * 1e9  # MJy/sr in one pixel -> mJy
BIN_R = 40  # resolving power of the binned spectrum (SPHEREx is R~35-130)


@lru_cache(maxsize=1)
def load_targets() -> dict[str, dict]:
    data = json.loads(TARGETS_PATH.read_text(encoding="utf-8"))
    return {t["id"]: t for t in data["targets"]}


def position_at(target: dict | None, ra: float, dec: float, mjd: float) -> tuple[float, float]:
    """Move (ra, dec), given for 2026.0, to the frame date using the target's proper motion."""
    if not target or target.get("pmra_mas_yr") is None:
        return ra, dec
    dt = (mjd - Time(2026.0, format="jyear").mjd) / 365.25
    ddec = target["pmdec_mas_yr"] * dt / 3.6e6
    dra = target["pmra_mas_yr"] * dt / 3.6e6 / np.cos(np.radians(dec))
    return ra + dra, dec + ddec


def photometry(c: Cutout, ra: float, dec: float) -> dict[str, float] | None:
    """Sky-subtracted aperture flux at (ra, dec), in mJy, plus wavelength there."""
    x, y = c.wcs.all_world2pix(ra, dec, 0)
    x, y = float(x), float(y)
    ny, nx = c.img.shape
    if not (SKY_R[1] <= x < nx - SKY_R[1] and SKY_R[1] <= y < ny - SKY_R[1]):
        return None
    yy, xx = np.mgrid[0:ny, 0:nx]
    r = np.hypot(xx - x, yy - y)
    ap = r <= AP_R
    sky = (r >= SKY_R[0]) & (r <= SKY_R[1])
    if np.isnan(c.img[ap]).any():  # flagged pixel on the star: skip, don't guess
        return None
    sky_v = c.img[sky][np.isfinite(c.img[sky])]
    if sky_v.size < 10:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        med = float(np.median(sky_v))
        sky_sig = 1.4826 * float(np.median(np.abs(sky_v - med)))
    n = int(ap.sum())
    flux = float(np.sum(c.img[ap]) - n * med)
    var = float(np.nansum(c.var[ap])) + n**2 * sky_sig**2 * np.pi / 2 / sky_v.size
    if not np.isfinite(flux) or not np.isfinite(var) or var <= 0:
        return None
    iy, ix = int(round(y)), int(round(x))
    wave = float(c.wave[iy, ix])
    if not np.isfinite(wave):
        return None
    return {
        "wavelength_um": round(wave, 4),
        "flux": flux * MJY_SR_TO_MJY,
        "err": float(np.sqrt(var)) * MJY_SR_TO_MJY,
    }


def bin_spectrum(points: list[dict], r: float = BIN_R) -> list[dict]:
    """Combine points into log-spaced bins, with 3-sigma clipping (cosmic rays, blends)."""
    if not points:
        return []
    wl = np.array([p["wavelength_um"] for p in points])
    fx = np.array([p["flux"] for p in points])
    er = np.array([p["err"] for p in points])
    edges = np.exp(np.arange(np.log(0.75), np.log(5.0) + 1 / r, 1 / r))
    out = []
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        m = (wl >= lo) & (wl < hi)
        if m.sum() == 0:
            continue
        f, e = fx[m], er[m]
        keep = np.ones(f.size, bool)
        if f.size >= 4:
            med = np.median(f)
            mad = 1.4826 * np.median(np.abs(f - med)) or np.median(e)
            keep = np.abs(f - med) <= 3 * max(mad, 1e-12)
        f, e, w = f[keep], e[keep], wl[m][keep]
        wt = 1 / e**2
        mean = float(np.sum(wt * f) / np.sum(wt))
        err = float(np.sqrt(1 / np.sum(wt)))
        if f.size > 2:  # don't trust the formal error if the points scatter more
            chi2 = float(np.sum(wt * (f - mean) ** 2) / (f.size - 1))
            err *= max(1.0, np.sqrt(chi2))
        out.append(
            {
                "wavelength_um": round(float(np.mean(w)), 4),
                "flux": round(mean, 5),
                "err": round(err, 5),
                "n": int(f.size),
            }
        )
    return out


def blends(ra: float, dec: float, mjds: list[float], target: dict | None) -> list[dict]:
    """Gaia stars inside the aperture: their light is mixed into this spectrum."""
    if not mjds:
        return []
    from api.science.ghosts import _gaia_cached, propagate

    try:
        stars = _gaia_cached(ra, dec, 0.02)
    except Exception:  # Gaia archive down: say nothing rather than fail the spectrum
        return []
    mid = float(np.median(mjds))
    tra, tdec = position_at(target, ra, dec, mid)
    pos = propagate(stars, np.array([mid])) if stars else []
    out = []
    for s, p in zip(stars, pos, strict=True):
        d = float(np.hypot((p[0, 0] - tra) * np.cos(np.radians(tdec)), p[0, 1] - tdec)) * 3600
        if 1.0 < d <= (AP_R + 1) * PIXEL_SCALE_ARCSEC:  # < 1": that's the target itself
            out.append(
                {"source_id": s["source_id"], "g_mag": s["g_mag"], "sep_arcsec": round(d, 1)}
            )
    return sorted(out, key=lambda b: b["sep_arcsec"])


def build_spectrum(ra: float, dec: float, target_id: str | None = None) -> dict[str, Any]:
    ra, dec = round(ra, 4), round(dec, 4)
    key = f"{ra:.4f}_{dec:+.4f}_{target_id or 'none'}"
    cached = CACHE_DIR / "spectra" / f"{key}.json"
    if cached.exists():
        return dict(json.loads(cached.read_text()))

    target = load_targets().get(target_id) if target_id else None
    cuts, failed = fetch_cutouts(ra, dec, SPEC_FOV)
    points = []
    for c in cuts:
        pra, pdec = position_at(target, ra, dec, c.mjd)
        p = photometry(c, pra, pdec)
        if p:
            points.append(p | {"mjd": round(c.mjd, 4), "detector": c.detector})
    if points:
        epochs = split_epochs(np.array([p["mjd"] for p in points]))
        for p, e in zip(points, epochs, strict=True):
            p["epoch"] = int(e)
    for p in points:
        p["flux"], p["err"] = round(p["flux"], 5), round(p["err"], 5)
    points.sort(key=lambda p: p["wavelength_um"])

    binned = bin_spectrum(points)
    resp: dict[str, Any] = {
        "target": {"ra": ra, "dec": dec, "id": target_id},
        "units": {"wavelength": "um", "flux": "mJy"},
        "n_frames": len(cuts),
        "n_failed": failed,
        "points": points,
        "binned": binned,
        "features": None,
        "blends": blends(ra, dec, [p["mjd"] for p in points], target),
    }
    if target_id:
        resp["features"] = interpret(points, target_id, blended=bool(resp["blends"]))
    if not failed and points:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(resp))
    return resp
