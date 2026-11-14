import numpy as np

from api.science.features import interpret, load_features


def _spectrum(dips=(), bumps=(), noise=0.01):
    wl = np.linspace(0.75, 5.0, 102)
    flux = np.full_like(wl, 10.0)
    for c in dips:
        flux *= 1 - 0.5 * np.exp(-0.5 * ((wl - c) / 0.05) ** 2)
    for c in bumps:
        flux *= 1 + 0.5 * np.exp(-0.5 * ((wl - c) / 0.04) ** 2)
    return [{"wavelength_um": w, "flux": f, "err": noise * 10, "epoch": 1} for w, f in zip(wl, flux)]


def status(result, band_id):
    return next(b["status"] for b in result["bands"] if b["id"] == band_id)


def test_every_target_has_a_profile_and_every_band_a_ref():
    feats = load_features()
    for profile in feats["targets"].values():
        assert profile in feats["profiles"]
    for prof in feats["profiles"].values():
        for b in prof["bands"]:
            assert b["ref"] in feats["refs"]
            assert 0.75 <= b["lo"] < b["hi"] <= 5.0


def test_flat_spectrum_shows_nothing():
    r = interpret(_spectrum(), "wise-0855")
    assert r["seen"] == 0


def test_methane_dip_is_seen():
    r = interpret(_spectrum(dips=[3.35]), "wise-0855")
    assert status(r, "ch4_3.3") == "seen"
    assert status(r, "h2o_1.4") != "seen"


def test_comet_co2_emission_is_seen():
    r = interpret(_spectrum(bumps=[4.26]), "3i-atlas")
    assert status(r, "co2_4.26") == "seen"


def test_unknown_target_returns_none():
    assert interpret(_spectrum(), "not-a-target") is None
