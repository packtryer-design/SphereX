"""PSF photometry with SPHEREx's official ePSFs, fitting the target and nearby stars together.

Method follows the SPHEREx Explanatory Supplement Sect. 3.3 (also used by
github.com/themilan1337/spherex-flag-checker, MIT): weighted least squares for one PSF
amplitude per source plus a flat background on a 15x15 stamp, weights 1/VARIANCE.
Fitting the neighbours too separates their light from the target's instead of mixing it in
(WISE 0855 has a G=16.3 star 7" away, about 1 pixel).

The ePSF files hold a 21x21 grid of PSFs across each detector. Our cached cutouts don't keep
the detector position, but SPHEREx's filter puts wavelength along detector Y, so the pixel's
wavelength picks the grid row; we average that row's 21 PSFs.

The ePSFs come from the QR3 calibration release, and we apply them to DR1 frames too: the PSF
is set by the telescope optics, not the processing version. If they didn't match, the fit
quality (fit_ql) would rise, and fit_ql > 1 already inflates the error bars.
"""

from __future__ import annotations

from functools import lru_cache

import httpx
import numpy as np
from astropy.io import fits
from scipy.ndimage import map_coordinates

from api.imaging.config import CACHE_DIR

EPSF_BASE = "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/qr3/epsf"
EPSF_TAG = dict.fromkeys(range(1, 7), "cal-epsf-v1-2026-191") | {3: "cal-epsf-v2-2026-191"}
STAMP = 15  # px
MIN_GOOD = 20  # fewer usable pixels than this: no fit
MAX_COND = 1e12


def _epsf_path(det: int):
    p = CACHE_DIR / "epsf" / f"epsf_D{det}.fits"
    if not p.exists():
        tag = EPSF_TAG[det]
        r = httpx.get(f"{EPSF_BASE}/{tag}/{det}/epsf_D{det}_spx_{tag}.fits", timeout=120)
        r.raise_for_status()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(r.content)
        tmp.replace(p)
    return p


@lru_cache(maxsize=6)
def _epsf_table(det: int) -> tuple[np.ndarray, np.ndarray, int]:
    """Per grid row (BINY): median wavelength and mean oversampled PSF."""
    with fits.open(_epsf_path(det)) as h:
        t = h["EPSF"].data
        ovs = int(h["EPSF"].header["OVSMPX"])
        biny, cwave, psf = np.array(t["BINY"]), np.array(t["CWAVE"]), np.array(t["EPSF"])
    rows = np.unique(biny)
    waves = np.array([np.median(cwave[biny == b]) for b in rows])
    psfs = np.stack([psf[biny == b].mean(axis=0) for b in rows])
    return waves, psfs, ovs


def epsf_for(det: int, wave_um: float) -> tuple[np.ndarray, int]:
    waves, psfs, ovs = _epsf_table(det)
    return psfs[int(np.argmin(np.abs(waves - wave_um)))], ovs


def render(epsf: np.ndarray, ovs: int, dx: np.ndarray, dy: np.ndarray) -> np.ndarray:
    """PSF value at native-pixel offsets (dx, dy) from the source, normalised over the stamp."""
    cy, cx = (np.array(epsf.shape) - 1) / 2
    v = map_coordinates(epsf, [cy + dy * ovs, cx + dx * ovs], order=1, mode="constant", cval=0.0)
    s = v.sum()
    return v / s if s > 0 else v


def fit(
    img: np.ndarray,
    var: np.ndarray,
    sources: list[tuple[float, float]],
    epsf: np.ndarray,
    ovs: int,
) -> dict | None:
    """Joint fit. sources[0] is the target, the rest are neighbours (pixel x, y).

    Returns amplitudes and 1-sigma errors in image units summed over the PSF (MJy/sr * px),
    plus fit_ql = mean |residual|/sigma within 2.5 px of the target (~1 is a good fit).
    """
    x0, y0 = sources[0]
    ny, nx = img.shape
    h = STAMP // 2
    ix, iy = int(round(x0)), int(round(y0))
    ys, xs = slice(max(iy - h, 0), min(iy + h + 1, ny)), slice(max(ix - h, 0), min(ix + h + 1, nx))
    d, v = img[ys, xs].astype(float), var[ys, xs].astype(float)
    yy, xx = np.mgrid[ys, xs]
    good = np.isfinite(d) & np.isfinite(v) & (v > 0)
    if good.sum() < MIN_GOOD:
        return None
    models = [render(epsf, ovs, xx - sx, yy - sy) for sx, sy in sources]
    a = np.stack([m[good] for m in models] + [np.ones(good.sum())], axis=1)
    w = 1 / v[good]
    ata = a.T @ (a * w[:, None])
    if not np.all(np.isfinite(ata)) or np.linalg.cond(ata) > MAX_COND:
        return None
    cov = np.linalg.inv(ata)
    p = cov @ (a.T @ (w * d[good]))
    resid = np.full(d.shape, np.nan)
    resid[good] = (d[good] - a @ p) / np.sqrt(v[good])
    core = np.hypot(xx - x0, yy - y0) <= 2.5
    ql = float(np.nanmean(np.abs(resid[core]))) if np.isfinite(resid[core]).any() else np.nan
    err = np.sqrt(np.diag(cov))
    return {"amp": p[:-1], "err": err[:-1], "bkg": float(p[-1]), "fit_ql": ql}
