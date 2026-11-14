"""Turn SPHEREx cutouts into a spectrum: one flux point per frame.

Each SPHEREx frame sees the target at a single wavelength (the linear variable
filter puts a different wavelength on every row), so stacking every frame that
covers a star gives its whole 0.75-5 um spectrum.

Flux per frame comes from a joint ePSF fit of the target and any Gaia star within
NEIGHBOUR_PX (psf.py); plain aperture photometry is the fallback when the fit can't run.
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
from api.science.psf import epsf_for, fit

TARGETS_PATH = Path(__file__).resolve().parents[2] / "data" / "targets.json"
SPEC_FOV = 0.03  # deg; small cutouts, just enough for aperture + sky annulus
AP_R = 2.0  # px aperture radius (PSF FWHM is ~1-2 px)
SKY_R = (4.0, 7.0)  # px sky annulus
PIX_SR = (PIXEL_SCALE_ARCSEC / 206264.806) ** 2
MJY_SR_TO_MJY = PIX_SR * 1e9  # MJy/sr in one pixel -> mJy
BIN_R = 40  # resolving power of the binned spectrum (SPHEREx is R~35-130)
SYS_FRAC = 0.03  # calibration floor, SPHEREx Explanatory Supplement Eq. 19
NEIGHBOUR_PX = 4.0  # Gaia stars this close are fitted together with the target
RESOLVE_PX = 0.5  # closer than this two PSFs are degenerate: light stays mixed (unresolved)
SELF_ARCSEC = 1.0  # Gaia star this close to the target position is the target itself
CORE_PX = 1.0  # flagged pixel this close to the source: skip the frame, don't guess
W2_BAND = (4.2, 5.0)  # um, part of WISE W2 (4.0-5.3) that SPHEREx covers well
W2_ZERO_MJY = 171787.0  # W2 Vega zero point, 171.787 Jy (Jarrett et al. 2011, ApJ 735, 112)
ALLWISE_MJD = 55400.0  # ~2010.5, mean AllWISE epoch
W2_MATCH_ARCSEC = 4.0
SAT_NOTE = (
    "Too bright for SPHEREx: the star saturated the detector in {} of {} frames, "
    "and those frames are left out rather than guessed."
)


def _with_floor(flux: float, err: float) -> float:
    return float(np.hypot(err, SYS_FRAC * abs(flux)))


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
        "err": _with_floor(flux, float(np.sqrt(var))) * MJY_SR_TO_MJY,
        "method": "aperture",
    }


def _core_flagged(c: Cutout, ra: float, dec: float) -> bool:
    """Flagged (NaN) pixel on the source: almost always saturation for our targets."""
    x, y = (float(v) for v in c.wcs.all_world2pix(ra, dec, 0))
    ny, nx = c.img.shape
    if not (0 <= x < nx and 0 <= y < ny):
        return False
    yy, xx = np.mgrid[0:ny, 0:nx]
    return bool(np.isnan(c.img[np.hypot(xx - x, yy - y) <= CORE_PX]).any())


def psf_photometry(
    c: Cutout, ra: float, dec: float, neighbours: list[tuple[float, float]] = ()
) -> dict[str, float] | None:
    """Joint ePSF fit of the target and neighbours (RA/Dec), target flux in mJy."""
    x, y = (float(v) for v in c.wcs.all_world2pix(ra, dec, 0))
    ny, nx = c.img.shape
    if not (2 <= x < nx - 2 and 2 <= y < ny - 2):
        return None
    if _core_flagged(c, ra, dec):
        return None
    wave = float(c.wave[int(round(y)), int(round(x))])
    if not np.isfinite(wave):
        return None
    srcs = [(x, y)]
    for nra, ndec in neighbours:
        sx, sy = (float(v) for v in c.wcs.all_world2pix(nra, ndec, 0))
        if 0 <= sx < nx and 0 <= sy < ny:
            srcs.append((sx, sy))
    try:
        epsf, ovs = epsf_for(c.detector, wave)
    except Exception:  # ePSF file unavailable: caller falls back to the aperture
        return None
    r = fit(c.img, c.var, srcs, epsf, ovs)
    if r is None or not np.isfinite(r["amp"][0]):
        return None
    flux, err = float(r["amp"][0]), float(r["err"][0])
    if np.isfinite(r["fit_ql"]):
        err *= max(1.0, r["fit_ql"])  # residuals above noise: PSF model is off, widen the error
    return {
        "wavelength_um": round(wave, 4),
        "flux": flux * MJY_SR_TO_MJY,
        "err": _with_floor(flux, err) * MJY_SR_TO_MJY,
        "method": "psf",
        "fit_ql": round(r["fit_ql"], 2) if np.isfinite(r["fit_ql"]) else None,
        "n_fit": len(srcs),
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
    from api.science.catalogs import gaia_cached
    from api.science.ghosts import propagate

    try:
        stars = gaia_cached(ra, dec, 0.02)
    except Exception:  # Gaia archive down: say nothing rather than fail the spectrum
        return []
    mid = float(np.median(mjds))
    tra, tdec = position_at(target, ra, dec, mid)
    pos = propagate(stars, np.array([mid])) if stars else []
    out = []
    for s, p in zip(stars, pos, strict=True):
        d = float(np.hypot((p[0, 0] - tra) * np.cos(np.radians(tdec)), p[0, 1] - tdec)) * 3600
        if SELF_ARCSEC < d <= (AP_R + 1) * PIXEL_SCALE_ARCSEC:
            out.append(
                {
                    "source_id": s["source_id"],
                    "g_mag": s["g_mag"],
                    "sep_arcsec": round(d, 1),
                    # separated by the PSF fit; closer than RESOLVE_PX it stays mixed in
                    "fitted": RESOLVE_PX * PIXEL_SCALE_ARCSEC
                    < d
                    <= NEIGHBOUR_PX * PIXEL_SCALE_ARCSEC,
                }
            )
    return sorted(out, key=lambda b: b["sep_arcsec"])


def w2_check(
    ra: float, dec: float, binned: list[dict], target: dict | None
) -> dict[str, Any] | None:
    """Compare our 4.2-5.0 um flux with WISE's W2 band (4.6 um) from AllWISE.

    Independent check that the photometry is on the right scale. Expect agreement within
    ~20%: W2 runs to 5.3 um where SPHEREx stops, and variable stars change between 2010
    and 2025.
    """
    from api.science.catalogs import allwise_cached

    band = [b for b in binned if W2_BAND[0] <= b["wavelength_um"] <= W2_BAND[1]]
    if len(band) < 3:
        return None
    wra, wdec = position_at(target, ra, dec, ALLWISE_MJD)
    try:
        rows = allwise_cached(round(wra, 4), round(wdec, 4), W2_MATCH_ARCSEC / 3600)
    except Exception:  # IRSA busy: skip the check, don't fail the spectrum
        return None
    rows = [r for r in rows if r["w2_mag"] is not None and r["ra"] is not None]
    if not rows:
        return None
    cosd = np.cos(np.radians(wdec))
    w = min(rows, key=lambda r: np.hypot((r["ra"] - wra) * cosd, r["dec"] - wdec))
    ours = float(np.mean([b["flux"] for b in band]))
    ours_err = float(np.sqrt(np.sum([b["err"] ** 2 for b in band])) / len(band))
    wise = W2_ZERO_MJY * 10 ** (-0.4 * w["w2_mag"])
    return {
        "catalog_id": w["source_id"],
        "w2_mag": w["w2_mag"],
        "wise_mJy": round(wise, 4),
        "spherex_mJy": round(ours, 4),
        "spherex_err": round(ours_err, 4),
        "ratio": round(ours / wise, 3) if wise > 0 else None,
        "wise_saturated": w["w2_sat"] > 0.05,  # W2 then unreliable: compare loosely
    }


def _neighbour_track(ra: float, dec: float, mjds: list[float]):
    """f(mjd, target_ra, target_dec) -> RA/Dec of Gaia stars to fit alongside the target."""
    if not mjds:
        return lambda *_: []
    from api.science.catalogs import gaia_cached
    from api.science.ghosts import propagate

    try:
        stars = gaia_cached(ra, dec, 0.02)
    except Exception:
        stars = []
    if not stars:
        return lambda *_: []
    t = np.array([min(mjds), max(mjds)])
    pos = propagate(stars, t)  # linear between the ends is plenty within a year
    reach = NEIGHBOUR_PX * PIXEL_SCALE_ARCSEC / 3600
    inner = RESOLVE_PX * PIXEL_SCALE_ARCSEC / 3600

    def at(mjd: float, tra: float, tdec: float) -> list[tuple[float, float]]:
        f = 0.0 if t[1] == t[0] else (mjd - t[0]) / (t[1] - t[0])
        p = pos[:, 0] + f * (pos[:, 1] - pos[:, 0])
        d = np.hypot((p[:, 0] - tra) * np.cos(np.radians(tdec)), p[:, 1] - tdec)
        keep = (d > inner) & (d <= reach)  # inner: target itself, or unresolvable twin
        return [(float(a), float(b)) for a, b in p[keep]]

    return at


def build_spectrum(ra: float, dec: float, target_id: str | None = None) -> dict[str, Any]:
    ra, dec = round(ra, 4), round(dec, 4)
    key = f"v4_{ra:.4f}_{dec:+.4f}_{target_id or 'none'}"  # v4: + fit_ql errors, saturation count
    cached = CACHE_DIR / "spectra" / f"{key}.json"
    if cached.exists():
        return dict(json.loads(cached.read_text()))

    target = load_targets().get(target_id) if target_id else None
    cuts, failed = fetch_cutouts(ra, dec, SPEC_FOV)
    points = []
    n_sat = 0
    nb = _neighbour_track(ra, dec, [c.mjd for c in cuts])
    for c in cuts:
        pra, pdec = position_at(target, ra, dec, c.mjd)
        p = psf_photometry(c, pra, pdec, nb(c.mjd, pra, pdec)) or photometry(c, pra, pdec)
        if p:
            points.append(p | {"mjd": round(c.mjd, 4), "detector": c.detector})
        elif _core_flagged(c, pra, pdec):
            n_sat += 1
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
        "n_saturated": n_sat,
        "saturation_note": SAT_NOTE.format(n_sat, len(cuts)) if n_sat > len(cuts) / 2 else None,
        "points": points,
        "binned": binned,
        "features": None,
        "blends": blends(ra, dec, [p["mjd"] for p in points], target),
        "photometry": {
            "psf": sum(p["method"] == "psf" for p in points),
            "aperture": sum(p["method"] == "aperture" for p in points),
            "sys_floor": SYS_FRAC,
        },
        "w2_check": w2_check(ra, dec, binned, target),
    }
    if target_id:
        ph = resp["photometry"]
        unseparated = any(not b["fitted"] for b in resp["blends"]) or ph["aperture"] > ph["psf"]
        resp["features"] = interpret(
            points, target_id, blended=bool(resp["blends"]) and unseparated
        )
    if not failed and points:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(resp))
    return resp
