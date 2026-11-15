"""Measure how fast a nearby star moves across the sky, from SPHEREx frames alone.

For every frame we fit the official ePSF to the star with its position free (psf.py does the
flux; here the position is the unknown), turn the best pixel position into RA/Dec with the
frame's WCS, and then fit a straight-line motion through all frames. The yearly parallax wobble
is put in from the catalogue parallax (two visits six months apart can't separate it from
motion), so what we measure is the proper motion, which we compare with Gaia/SIMBAD.

Saturated frames (most of Barnard's Star's) still count. Their flagged core is too big for the
ePSF, which reaches only ~3 px, so there the centre is found by symmetry instead: the point
about which the star's unflagged wings best match themselves turned 180 degrees.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
from astropy.coordinates import get_body_barycentric
from astropy.time import Time
from scipy.ndimage import binary_dilation, map_coordinates
from scipy.optimize import minimize

from api.imaging.cutouts import Cutout, fetch_cutouts
from api.imaging.pipeline import split_epochs
from api.science.psf import STAMP, epsf_for, render
from api.science.spectrum import SPEC_FOV, _neighbour_track, load_targets, position_at

T0 = Time(2026.0, format="jyear")
MAX_SHIFT_PX = 1.5  # the fitted centre may wander this far from the catalogue prediction
MIN_SNR = 4.0  # fainter than this in one frame: centre too uncertain to use
MAX_CHI2 = 4.0  # reduced chi2 worse than this: blend, artefact or edge, skip the frame
CLIP = 4.0  # robust outlier cut, in units of the scatter


def parallax_factors(mjd: np.ndarray, ra: float, dec: float) -> tuple[np.ndarray, np.ndarray]:
    """Shift (east, north) per arcsec of parallax, seen from Earth on each date."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # ERFA "dubious year"
        e = get_body_barycentric("earth", Time(mjd, format="mjd")).xyz.to_value("AU")
    a, d = np.radians(ra), np.radians(dec)
    x, y, z = e
    east = x * np.sin(a) - y * np.cos(a)
    north = x * np.cos(a) * np.sin(d) + y * np.sin(a) * np.sin(d) - z * np.cos(d)
    return east, north


def _stamp(c: Cutout, x0: float, y0: float):
    h = STAMP // 2
    ix, iy = int(round(x0)), int(round(y0))
    ys, xs = slice(iy - h, iy + h + 1), slice(ix - h, ix + h + 1)
    d, v = c.img[ys, xs].astype(float), c.var[ys, xs].astype(float)
    yy, xx = np.mgrid[ys, xs]
    good = np.isfinite(d) & np.isfinite(v) & (v > 0)
    return d[good], 1 / v[good], xx[good], yy[good]


def _solve(d, w, xx, yy, x, y, epsf, ovs, others=()):
    """PSF amplitudes (target at x, y; Gaia neighbours fixed) + flat background.

    Returns (chi2, target amplitude, its error)."""
    cols = [render(epsf, ovs, xx - x, yy - y)]
    cols += [render(epsf, ovs, xx - ox, yy - oy) for ox, oy in others]
    a = np.stack([*cols, np.ones(d.size)], axis=1)
    ata = a.T @ (a * w[:, None])
    if np.linalg.cond(ata) > 1e12:
        return 1e30, 0.0, np.inf
    cov = np.linalg.inv(ata)
    p = cov @ (a.T @ (w * d))
    return float(np.sum(w * (d - a @ p) ** 2)), float(p[0]), float(np.sqrt(cov[0, 0]))


def _symmetry_centre(c: Cutout, x0: float, y0: float) -> tuple[float, float] | None:
    """Centre of a saturated star: where its wings best match their own 180-degree turn."""
    ny, nx = c.img.shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    flagged = ~np.isfinite(c.img)
    near = np.hypot(xx - x0, yy - y0) <= 7
    if not (flagged & near).any():
        return None
    # Pixels touching the flagged core are non-linear even when not flagged: drop them too.
    bad = binary_dilation(flagged, iterations=1)
    img = np.where(bad, np.nan, c.img.astype(float))
    sig = np.sqrt(np.where(c.var > 0, c.var, np.nan))
    use = near & ~bad & np.isfinite(sig)
    if use.sum() < 30:
        return None
    px, py, pv, ps = xx[use], yy[use], img[use], sig[use]
    hole = flagged & near
    start = (float(xx[hole].mean()), float(yy[hole].mean()))

    def cost(p: np.ndarray) -> float:
        if np.hypot(p[0] - x0, p[1] - y0) > MAX_SHIFT_PX + 1:
            return 1e30
        tx, ty = 2 * p[0] - px, 2 * p[1] - py
        tv = map_coordinates(img, [ty, tx], order=1, mode="constant", cval=np.nan)
        ok = np.isfinite(tv)
        if ok.sum() < 20:
            return 1e30
        return float(np.mean(((pv[ok] - tv[ok]) / ps[ok]) ** 2))

    best = minimize(cost, np.array(start), method="Nelder-Mead", options={"xatol": 0.005})
    if best.fun >= 1e29:
        return None
    return float(best.x[0]), float(best.x[1])


def _psf_centre(
    c: Cutout, x0: float, y0: float, others: list[tuple[float, float]]
) -> tuple[float, float] | None:
    wave = float(c.wave[int(round(y0)), int(round(x0))])
    if not np.isfinite(wave):
        return None
    try:
        epsf, ovs = epsf_for(c.detector, wave)
    except Exception:
        return None
    d, w, xx, yy = _stamp(c, x0, y0)
    if d.size < STAMP**2 * 0.8:
        return None

    def chi2(p: np.ndarray) -> float:
        if np.hypot(*p) > MAX_SHIFT_PX:
            return 1e30
        return _solve(d, w, xx, yy, x0 + p[0], y0 + p[1], epsf, ovs, others)[0]

    grid = [np.array([dx, dy]) for dx in (-0.6, 0, 0.6) for dy in (-0.6, 0, 0.6)]
    start = min(grid, key=chi2)
    best = minimize(chi2, start, method="Nelder-Mead", options={"xatol": 0.005, "fatol": 1e-3})
    c2, amp, err = _solve(d, w, xx, yy, x0 + best.x[0], y0 + best.x[1], epsf, ovs, others)
    if (
        c2 / (d.size - 4 - len(others)) > MAX_CHI2
        or amp <= MIN_SNR * err
        or np.hypot(*best.x) >= MAX_SHIFT_PX
    ):
        return None
    return x0 + float(best.x[0]), y0 + float(best.x[1])


def fit_position(
    c: Cutout, ra: float, dec: float, neighbours: list[tuple[float, float]] = ()
) -> dict[str, Any] | None:
    """Measured RA/Dec of the star in one frame, or None if the frame can't say."""
    x0, y0 = (float(v) for v in c.wcs.all_world2pix(ra, dec, 0))
    ny, nx = c.img.shape
    if not (8 <= x0 < nx - 8 and 8 <= y0 < ny - 8):
        return None
    saturated = bool(
        (
            ~np.isfinite(
                c.img[
                    int(round(y0)) - 1 : int(round(y0)) + 2, int(round(x0)) - 1 : int(round(x0)) + 2
                ]
            )
        ).any()
    )
    others = [tuple(float(v) for v in c.wcs.all_world2pix(a, b, 0)) for a, b in neighbours]
    xy = _symmetry_centre(c, x0, y0) if saturated else _psf_centre(c, x0, y0, others)
    if xy is None:
        return None
    fra, fdec = (float(v) for v in c.wcs.all_pix2world(xy[0], xy[1], 0))
    return {"ra": fra, "dec": fdec, "saturated": saturated}


def measure_motion(target_id: str) -> dict[str, Any]:
    t = load_targets()[target_id]
    ra, dec = round(t["ra_2026"], 4), round(t["dec_2026"], 4)  # same cutouts as the spectrum
    cuts, _ = fetch_cutouts(ra, dec, SPEC_FOV)
    rows = []
    nb = _neighbour_track(ra, dec, [c.mjd for c in cuts])  # Gaia stars to fit alongside
    for c in cuts:
        pra, pdec = position_at(t, ra, dec, c.mjd)
        p = fit_position(c, pra, pdec, nb(c.mjd, pra, pdec))
        if p:
            rows.append(p | {"mjd": c.mjd})
    if len(rows) < 6:
        return {"id": target_id, "ok": False, "reason": f"only {len(rows)} usable frames"}

    mjd = np.array([r["mjd"] for r in rows])
    cosd = np.cos(np.radians(dec))
    east = (np.array([r["ra"] for r in rows]) - ra) * cosd * 3600
    north = (np.array([r["dec"] for r in rows]) - dec) * 3600
    yr = (mjd - T0.mjd) / 365.25
    plx = t["plx_mas"] / 1000
    pe, pn = parallax_factors(mjd, ra, dec)
    # Positions in targets.json are astrometric (no parallax), so remove the catalogue parallax.
    east, north = east - plx * pe, north - plx * pn

    keep = np.ones(len(rows), bool)
    for _ in range(5):  # straight line per axis with robust clipping
        a = np.stack([np.ones(keep.sum()), yr[keep]], axis=1)
        ce, *_ = np.linalg.lstsq(a, east[keep], rcond=None)
        cn, *_ = np.linalg.lstsq(a, north[keep], rcond=None)
        re = east - (ce[0] + ce[1] * yr)
        rn = north - (cn[0] + cn[1] * yr)
        rr = np.hypot(re, rn)
        s = 1.4826 * np.median(rr[keep])
        new = rr <= CLIP * max(s, 0.05)
        if (new == keep).all():
            break
        keep = new

    n = int(keep.sum())
    a = np.stack([np.ones(n), yr[keep]], axis=1)
    sig = float(np.sqrt(np.mean(np.concatenate([re[keep], rn[keep]]) ** 2)))  # per-frame scatter
    cov = np.linalg.inv(a.T @ a) * sig**2
    pm_err = float(np.sqrt(cov[1, 1]))  # from frame-to-frame scatter alone
    pm_e, pm_n = float(ce[1]), float(cn[1])
    cat_e, cat_n = t["pmra_mas_yr"] / 1000, t["pmdec_mas_yr"] / 1000
    total, cat_total = float(np.hypot(pm_e, pm_n)), float(np.hypot(cat_e, cat_n))

    epochs = split_epochs(mjd[keep])
    per_epoch = []
    for e in np.unique(epochs):
        m = epochs == e
        per_epoch.append(
            {
                "epoch": int(e),
                "date": Time(float(np.median(mjd[keep][m])), format="mjd").to_value("iso", "date"),
                "n": int(m.sum()),
                "east_arcsec": round(float(np.median(east[keep][m])), 2),
                "north_arcsec": round(float(np.median(north[keep][m])), 2),
            }
        )
    # Each visit can sit slightly off as a whole (its astrometric solution, its mix of
    # wavelengths). With 3+ visits, measure that from how far visit averages miss the line
    # and add it to the error, so the error bar isn't optimistic.
    sys_err = 0.0
    if len(per_epoch) >= 3:
        te = np.array([np.median(yr[keep][epochs == e["epoch"]]) for e in per_epoch])
        off = [
            np.hypot(
                e["east_arcsec"] - (ce[0] + ce[1] * x), e["north_arcsec"] - (cn[0] + cn[1] * x)
            )
            for e, x in zip(per_epoch, te, strict=True)
        ]
        visit_sig = float(np.sqrt(np.sum(np.square(off)) / (2 * (len(off) - 2))))
        sys_err = visit_sig / float(np.sqrt(np.sum((te - te.mean()) ** 2)))
    pm_err = float(np.hypot(pm_err, sys_err))
    span = float(yr[keep].max() - yr[keep].min())
    return {
        "id": target_id,
        "name": t["name"],
        "ok": True,
        "n_frames": len(cuts),
        "n_used": n,
        "span_days": round(span * 365.25),
        "per_frame_scatter_arcsec": round(sig, 2),
        "measured": {
            "pm_arcsec_yr": round(total, 2),
            "err": round(pm_err, 2),
            "pm_east": round(pm_e, 2),
            "pm_north": round(pm_n, 2),
        },
        "catalogue": {
            "pm_arcsec_yr": round(cat_total, 2),
            "pm_east": round(cat_e, 3),
            "pm_north": round(cat_n, 3),
        },
        "difference_sigma": round(abs(total - cat_total) / pm_err, 1) if pm_err > 0 else None,
        "moved_arcsec": round(total * span, 1),
        "epochs": per_epoch,
    }
