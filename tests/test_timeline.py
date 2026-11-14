"""Offline tests for the time-comparison additions: visit lists, diff references, spectra."""

from typing import Any

import numpy as np
import pytest
from api.imaging import pipeline, visits
from api.imaging.cutouts import Cutout
from api.science import surface
from astropy.wcs import WCS


def _frames(spec: list[tuple[int, int, float]]) -> tuple[list[dict[str, Any]], list[np.ndarray]]:
    """(epoch, detector, value) -> frame dicts and flat images of that value."""
    frames = [
        {
            "mjd": 100.0 * e + i * 0.1,
            "detector": d,
            "wavelength_um": 1.0,
            "n_frames": 1,
            "flagged_frac": 0.0,
            "epoch": e,
        }
        for i, (e, d, _) in enumerate(spec)
    ]
    return frames, [np.full((3, 3), v) for _, _, v in spec]


def test_epoch_meta_lists_detectors_and_dates() -> None:
    frames, zs = _frames([(1, 1, 0.0), (1, 2, 0.0), (2, 2, 0.0)])
    _, out = pipeline._combine(frames, zs, "epoch", "all")
    assert [f["detectors"] for f in out] == [[1, 2], [2]]
    assert out[0]["mjd_start"] == 100.0 and out[0]["mjd_end"] == 100.1


def test_diff_uses_only_shared_detectors() -> None:
    # epoch 1 has D1 (value 0) and D2 (value 0); epoch 2 has only D2 (value 4).
    # D1 must not leak into the difference as fake change.
    frames, zs = _frames([(1, 1, 0.0), (1, 2, 0.0), (2, 2, 4.0)])
    images, out = pipeline._combine(frames, zs, "diff", "all")
    assert len(out) == 1
    assert out[0]["detectors"] == [2]
    assert out[0]["ref_epoch"] == 1
    assert np.allclose(images[0], 4.0)


def test_diff_against_a_chosen_reference() -> None:
    frames, zs = _frames([(1, 1, 1.0), (2, 1, 3.0), (3, 1, 6.0)])
    images, out = pipeline._combine(frames, zs, "diff", "all", ref=2)
    assert [f["epoch"] for f in out] == [1, 3]
    assert np.allclose(images[0], -2.0) and np.allclose(images[1], 3.0)


def test_rgb_reports_its_epochs() -> None:
    frames, zs = _frames([(1, 1, 1.0), (2, 1, 2.0), (3, 1, 3.0)])
    _, out = pipeline._combine(frames, zs, "rgb", "all")
    assert out[0]["epochs"] == [1, 2, 3]


def test_list_visits_groups_real_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [("u", 0.0, d) for d in range(1, 7)] + [("u", 183.0, 2), ("u", 184.0, 5)]
    monkeypatch.setattr(visits, "query_frames", lambda ra, dec: rows)
    v = visits.list_visits(10.0, 20.0)["visits"]
    assert len(v) == 2
    assert v[0]["full_coverage"] and not v[1]["full_coverage"]
    assert v[1]["detectors"] == [2, 5]
    assert (v[1]["mjd_start"], v[1]["mjd_end"]) == (183.0, 184.0)


def test_list_visits_with_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(visits, "query_frames", lambda ra, dec: [])
    assert visits.list_visits(10.0, 20.0)["visits"] == []


def test_surface_spectrum_reads_each_cutout(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    ra, dec = 150.0, 2.0
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [6, 6]  # 1-based: pixel (5, 5) in numpy is the centre
    w.wcs.cdelt = [-6.15 / 3600, 6.15 / 3600]

    def cut(value: float, wave: float, mjd: float) -> Cutout:
        return Cutout(
            img=np.full((11, 11), value, dtype=np.float32),
            var=np.full((11, 11), 4.0, dtype=np.float32),
            wave=np.full((11, 11), wave, dtype=np.float32),
            wcs=w,
            mjd=mjd,
            detector=1,
            url="x",
        )

    cuts = [cut(2.0, 1.5, 0.0), cut(1.0, 0.9, 0.5), cut(3.0, 1.2, 200.0)]
    monkeypatch.setattr(surface, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(surface, "fetch_cutouts", lambda *a: (cuts, 0))
    s = surface.build_surface_spectrum(ra, dec, ra, dec, 0.05)
    assert [p["wavelength_um"] for p in s["points"]] == [0.9, 1.2, 1.5]  # sorted by wavelength
    assert [p["flux"] for p in s["points"]] == [1.0, 3.0, 2.0]
    assert [p["epoch"] for p in s["points"]] == [1, 2, 1]
    assert s["points"][0]["err"] == pytest.approx(np.sqrt(9 * 4.0) / 9)
