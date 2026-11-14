import numpy as np
from api.imaging.pipeline import align, make_rgb, split_epochs, target_grid
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


def test_still_star_is_white() -> None:
    a = np.random.default_rng(0).random((5, 5))
    rgb = make_rgb(a, a, a)
    assert np.array_equal(rgb[..., 0], rgb[..., 1]) and np.array_equal(rgb[..., 1], rgb[..., 2])
