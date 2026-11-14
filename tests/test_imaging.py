from typing import Any

import numpy as np
from api.imaging.pipeline import _matched_diff, align, make_rgb, split_epochs, target_grid
from astropy.wcs import WCS


def test_split_epochs_on_gaps() -> None:
    mjd = np.array([184.0, 0, 1, 2, 183, 366])
    assert split_epochs(mjd).tolist() == [2, 1, 1, 1, 2, 3]


def test_long_epoch_is_chunked() -> None:
    # no 30-day gap anywhere (as near the ecliptic poles), 90 days long -> chunks of 30 days
    mjd = np.arange(0.0, 90.0, 5.0)
    assert len(set(split_epochs(mjd).tolist())) == 3


def test_align_puts_star_on_centre() -> None:
    ra, dec = 269.4462, 4.7682
    src = WCS(naxis=2)
    src.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    src.wcs.crval = [ra + 0.01, dec - 0.01]  # frame not centred on the target
    src.wcs.crpix = [50, 50]
    s = 6.15 / 3600
    th = np.radians(37)  # rotated, like real SPHEREx frames
    src.wcs.cd = [[-s * np.cos(th), s * np.sin(th)], [s * np.sin(th), s * np.cos(th)]]
    x0, y0 = src.all_world2pix(ra, dec, 0)
    yy, xx = np.mgrid[:100, :100]
    img = np.exp(-((xx - x0) ** 2 + (yy - y0) ** 2) / (2 * 1.5**2))

    out_wcs, shape = target_grid(ra, dec, 0.05)
    out = align(img, src, out_wcs, shape)
    py, px = np.unravel_index(np.nanargmax(out), out.shape)
    c = (shape[0] - 1) / 2
    assert abs(px - c) <= 0.5 and abs(py - c) <= 0.5


def test_diff_cancels_colour_but_keeps_real_change() -> None:
    def frame(epoch: int, wl: float) -> dict[str, Any]:
        return {"epoch": epoch, "detector": 1, "wavelength_um": wl, "mjd": 0.0, "flagged_frac": 0}

    # star brightness depends on wavelength; epoch 2 has an extra frame at an unmatched colour
    frames = [
        frame(1, 1.0),
        frame(1, 2.0),
        frame(2, 1.01),
        frame(2, 2.0),
        frame(2, 3.0),
        frame(3, 4.0),
    ]
    zs = [np.full((3, 3), f["wavelength_um"] * 10) for f in frames]
    zs[3] = zs[3] + 5.0  # a real change in epoch 2 at 2.0 um

    def meta(e: int) -> dict[str, Any]:
        return {"epoch": e}

    images, out = _matched_diff(frames, zs, [1, 2, 3], [1], meta)
    assert [m["epoch"] for m in out] == [2]  # epoch 3 (4.0 um) has no match: left out
    assert out[0]["n_frames"] == 4  # 1.01 pairs with 1.0, 2.0 with 2.0; 3.0 unmatched
    # pairs give 0.1 (colour within the match tolerance) and 5.0; median of two = 2.55
    assert np.allclose(images[0], 2.55)


def test_still_star_is_white() -> None:
    a = np.random.default_rng(0).random((5, 5))
    rgb = make_rgb(a, a, a)
    assert np.array_equal(rgb[..., 0], rgb[..., 1]) and np.array_equal(rgb[..., 1], rgb[..., 2])
