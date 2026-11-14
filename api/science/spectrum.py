"""Spectrum at one sky position, measured from the same cutouts the flipbook uses.

Every SPHEREx frame sees a given spot through a slightly different wavelength (the
filters vary across each detector), so one point per frame, with its own wavelength
read from the frame's spectral WCS, adds up to a spectrum. Points keep their date and
epoch, so the front end can also compare the spectrum between visits.
"""

import json
import warnings
from typing import Any

import numpy as np

from api.imaging.config import CACHE_DIR
from api.imaging.cutouts import fetch_cutouts
from api.imaging.pipeline import split_epochs

BOX = 1  # half-width in pixels: average a 3x3 box (~18") to beat down pixel noise


def build_spectrum(
    ra: float, dec: float, field_ra: float, field_dec: float, fov: float
) -> dict[str, Any]:
    """Spectrum at (ra, dec), using the cutouts already fetched for the field centred on
    (field_ra, field_dec), so clicking around an open field never re-downloads anything."""
    ra, dec = round(ra, 5), round(dec, 5)
    field_ra, field_dec, fov = round(field_ra, 4), round(field_dec, 4), round(fov, 3)
    key = f"{ra:.5f}_{dec:+.5f}_{field_ra:.4f}_{field_dec:+.4f}_{fov:.3f}"
    cached = CACHE_DIR / "spectra" / f"{key}.json"
    if cached.exists():
        return dict(json.loads(cached.read_text()))

    cuts, failed = fetch_cutouts(field_ra, field_dec, fov)
    points: list[dict[str, Any]] = []
    for c in cuts:
        x, y = c.wcs.all_world2pix(ra, dec, 0)
        ix, iy = int(round(float(x))), int(round(float(y)))
        h, w = c.img.shape
        if not (BOX <= ix < w - BOX and BOX <= iy < h - BOX):
            continue
        img = c.img[iy - BOX : iy + BOX + 1, ix - BOX : ix + BOX + 1]
        var = c.var[iy - BOX : iy + BOX + 1, ix - BOX : ix + BOX + 1]
        good = np.isfinite(img) & np.isfinite(var) & (var > 0)
        n = int(good.sum())
        if n == 0 or not np.isfinite(c.wave[iy, ix]):
            continue
        points.append(
            {
                "wavelength_um": round(float(c.wave[iy, ix]), 4),
                "flux": float(img[good].mean()),
                "err": float(np.sqrt(var[good].sum()) / n),
                "mjd": round(c.mjd, 4),
                "detector": c.detector,
            }
        )

    if points:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            epochs = split_epochs(np.array([p["mjd"] for p in points]))
        for p, e in zip(points, epochs, strict=True):
            p["epoch"] = int(e)
        points.sort(key=lambda p: p["wavelength_um"])

    resp = {
        "target": {"ra": ra, "dec": dec},
        "unit": "MJy/sr",
        "note": "Surface brightness with zodiacal light subtracted; 3x3 pixel average.",
        "points": points,
    }
    if not failed:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(resp))
    return resp
