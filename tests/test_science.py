import numpy as np
from api.imaging.cutouts import Cutout
from api.science.ghosts import propagate
from api.science.spectrum import MJY_SR_TO_MJY, bin_spectrum, photometry, position_at
from astropy.wcs import WCS


def _cutout(star_x=12.0, star_y=12.0, amp=100.0, sky=5.0, n=25):
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [100.0, 10.0]
    w.wcs.crpix = [13, 13]  # 1-based: pixel 12 (0-based) is the centre
    w.wcs.cdelt = [-6.15 / 3600, 6.15 / 3600]
    yy, xx = np.mgrid[0:n, 0:n]
    star = amp * np.exp(-0.5 * ((xx - star_x) ** 2 + (yy - star_y) ** 2) / 0.6**2)
    img = sky + star
    return Cutout(
        img=img,
        var=np.full_like(img, 0.01),
        wave=np.full_like(img, 2.5),
        wcs=w,
        mjd=61000.0,
        detector=3,
        url="test",
    ), star


def test_photometry_recovers_star_flux_and_removes_sky():
    c, star = _cutout()
    p = photometry(c, 100.0, 10.0)
    assert p["wavelength_um"] == 2.5
    assert abs(p["flux"] - star.sum() * MJY_SR_TO_MJY) / (star.sum() * MJY_SR_TO_MJY) < 0.02
    assert p["err"] > 0


def test_photometry_skips_flagged_star_and_edges():
    c, _ = _cutout()
    c.img[12, 12] = np.nan
    assert photometry(c, 100.0, 10.0) is None
    c, _ = _cutout()
    assert photometry(c, 100.0 + 70 * 6.15 / 3600, 10.0) is None  # off the cutout


def test_bin_spectrum_clips_cosmic_ray():
    pts = [{"wavelength_um": 2.0 + i * 1e-4, "flux": 1.0, "err": 0.1} for i in range(9)]
    pts.append({"wavelength_um": 2.0005, "flux": 50.0, "err": 0.1})
    b = bin_spectrum(pts)
    assert len(b) == 1 and abs(b[0]["flux"] - 1.0) < 1e-6 and b[0]["n"] == 9


def test_position_at_uses_proper_motion():
    t = {"pmra_mas_yr": 0.0, "pmdec_mas_yr": 3600.0}  # 1 arcmin... per 1000 yr; 3.6"/yr
    ra, dec = position_at(t, 100.0, 10.0, 61041.0 + 365.25)  # ~2027.0
    assert abs((dec - 10.0) * 3600 - 3.6) < 0.05 and ra == 100.0
    assert position_at(None, 1.0, 2.0, 0.0) == (1.0, 2.0)


def test_propagate_barnards_star_moves_north():
    star = {"ra": 269.4485, "dec": 4.7394, "pmra": -801.6, "pmdec": 10362.4, "parallax": 546.98}
    pos = propagate([star], np.array([57388.0, 57388.0 + 365.25 * 10]))  # 2016.0 -> 2026.0
    assert abs((pos[0, 1, 1] - pos[0, 0, 1]) * 3600 - 103.6) < 1.0
