import numpy as np
from api.science import catalogs
from api.science.features import _excess
from api.science.ghosts import clean_catwise
from api.science.psf import fit, render
from api.science.spectrum import SYS_FRAC, photometry
from tests.test_science import _cutout


def _gauss_epsf(sigma=0.8, ovs=5, n=33):
    yy, xx = np.mgrid[0:n, 0:n] - (n - 1) / 2
    e = np.exp(-0.5 * (xx**2 + yy**2) / (sigma * ovs) ** 2)
    return e / e.sum(), ovs


def _scene(sources, bkg=3.0, n=25, noise=0.0, seed=0):
    epsf, ovs = _gauss_epsf()
    yy, xx = np.mgrid[0:n, 0:n]
    img = np.full((n, n), bkg)
    for x, y, a in sources:
        img += a * render(epsf, ovs, xx - x, yy - y)
    img += np.random.default_rng(seed).normal(0, noise, img.shape) if noise else 0
    return img, np.full_like(img, max(noise, 0.01) ** 2), epsf, ovs


def test_psf_fit_recovers_amplitude_and_background():
    img, var, epsf, ovs = _scene([(12.3, 11.6, 500.0)], noise=0.1)
    r = fit(img, var, [(12.3, 11.6)], epsf, ovs)
    assert abs(r["amp"][0] - 500) < 3 * r["err"][0] + 1
    assert abs(r["bkg"] - 3.0) < 0.05
    assert 0.5 < r["fit_ql"] < 1.2


def test_joint_fit_separates_neighbour_one_pixel_away():
    # WISE 0855-like: faint target, brighter star ~1.1 px away
    img, var, epsf, ovs = _scene([(12.0, 12.0, 100.0), (13.1, 12.2, 400.0)], noise=0.1)
    alone = fit(img, var, [(12.0, 12.0)], epsf, ovs)["amp"][0]
    joint = fit(img, var, [(12.0, 12.0), (13.1, 12.2)], epsf, ovs)["amp"]
    assert alone > 200  # ignoring the neighbour badly overestimates the target
    assert abs(joint[0] - 100) < 5 and abs(joint[1] - 400) < 5


def test_psf_fit_needs_enough_good_pixels():
    img, var, epsf, ovs = _scene([(12.0, 12.0, 100.0)])
    img[:, :] = np.nan
    img[12, 10:20] = 1.0
    assert fit(img, var, [(12.0, 12.0)], epsf, ovs) is None


def test_error_floor_is_three_percent():
    c, _ = _cutout(amp=1e6)  # bright: photon error tiny, floor dominates
    p = photometry(c, 100.0, 10.0)
    assert abs(p["err"] / p["flux"] - SYS_FRAC) < 1e-3


def test_catwise_rows_convert_arcsec_to_mas(monkeypatch):
    row = {
        "source_name": " J085510.74-071442.5 ",
        "ra_pm": "133.7948",
        "dec_pm": "-7.2453",
        "pmra": "-8.118",
        "pmdec": "0.680",
        "w1mpro": "",
        "w2mpro": "13.89",
        "w2snr": "56.2",
        "sigpmra": "0.02",
        "sigpmdec": "0.02",
        "ab_flags": "00",
    }
    monkeypatch.setattr(catalogs, "_irsa_csv", lambda q: [row])
    (s,) = catalogs.catwise_cone(133.79, -7.24, 0.01)
    assert s["pmra"] == -8118.0 and abs(s["pmdec"] - 680.0) < 1e-9
    assert s["w1_mag"] is None and s["w2_mag"] == 13.89
    assert s["source_id"] == "CWISE J085510.74-071442.5"


def test_gaia_falls_back_to_irsa(monkeypatch):
    def busy(*a):
        raise RuntimeError("queue full")

    row = {
        "source_id": "4472832130942575872",
        "ra": "269.4485",
        "dec": "4.7394",
        "pmra": "-801.6",
        "pmdec": "10362.4",
        "parallax": "546.98",
        "phot_g_mean_mag": "8.19",
    }
    seen = []
    monkeypatch.setattr(catalogs, "_gaia_esa", busy)
    monkeypatch.setattr(catalogs, "_irsa_csv", lambda q: seen.append(q) or [row])
    (s,) = catalogs.gaia_cone(269.45, 4.74, 0.01)
    assert "gaia_dr3_source" in seen[0]
    assert s["g_mag"] == 8.19 and s["parallax"] == 546.98


def test_catwise_drops_artifacts_and_zeroes_weak_motion(monkeypatch):
    base = {"ra_pm": "10", "dec_pm": "0", "w1mpro": "", "w2mpro": "14", "ab_flags": "00"}
    rows = [
        base
        | {
            "source_name": "A",
            "pmra": "0.05",
            "pmdec": "0",
            "sigpmra": "0.03",
            "sigpmdec": "0.03",
            "w2snr": "40",
        },
        base
        | {
            "source_name": "B",
            "pmra": "0",
            "pmdec": "0",
            "sigpmra": "0.01",
            "sigpmdec": "0.01",
            "w2snr": "3",
        },
        base
        | {
            "source_name": "C",
            "pmra": "0",
            "pmdec": "0",
            "sigpmra": "0.01",
            "sigpmdec": "0.01",
            "w2snr": "40",
            "ab_flags": "0H",
        },
    ]
    monkeypatch.setattr(catalogs, "_irsa_csv", lambda q: rows)
    (s,) = catalogs.catwise_cone(10, 0, 0.01)
    assert s["source_id"] == "CWISE A" and s["pmra"] == 0.0


def _cw(name, ra, dec, pmra=0.0, w2=14.0):
    return {
        "source_id": name,
        "ra": ra,
        "dec": dec,
        "pmra": pmra,
        "pmdec": 0.0,
        "parallax": None,
        "w2_mag": w2,
    }


def test_clean_catwise_halo_duplicates_and_fragments():
    star = {
        "source_id": "g",
        "ra": 10.0,
        "dec": 0.0,
        "pmra": 0.0,
        "pmdec": 0.0,
        "parallax": None,
        "g_mag": 8.0,
    }
    far = 10.0 + 300 / 3600
    cw = [
        _cw("same", 10.0 + 1 / 3600, 0.0),  # the Gaia star itself
        _cw("halo", 10.0 + 60 / 3600, 0.0, pmra=9000.0),  # bright-star halo junk
        _cw("bd", far, 0.0, pmra=8000.0, w2=15.5),
        _cw("bd-piece", far + 15 / 3600, 0.0, pmra=8100.0, w2=15.8),  # same object
        _cw("neighbour", far + 15 / 3600, 0.0, w2=15.9),  # fixed source, kept
    ]
    kept = [s["source_id"] for s in clean_catwise(cw, [star])]
    assert kept == ["bd", "neighbour"]


def test_excess_lower_limit_when_reference_undetected():
    wl = np.array([2.1, 2.15, 4.3, 4.35])
    fx = np.array([0.0, 0.0, 1.0, 1.0])
    er = np.full(4, 0.01)
    contrast, sig, limit = _excess(wl, fx, er, 4.2, 4.4)
    assert limit and contrast > 10 and contrast / sig > 3
    fx2 = np.array([1.0, 1.0, 1.0, 1.0])
    *_, limit2 = _excess(wl, fx2, er, 4.2, 4.4)
    assert not limit2
