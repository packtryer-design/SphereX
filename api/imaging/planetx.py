"""Could SPHEREx find a new planet? Shift-and-stack search, tested on Pluto and planted planets.

A distant planet too faint for any single frame can still be found: shift every frame along a
guessed motion and add them up. Only something moving that way piles up; noise averages down
by sqrt(N). We try every plausible motion blind, then:
  1. check the search finds Pluto without being told where it is (a real planet), and
  2. plant a fake "Planet X" at the speed of a body ~300 AU away, fainter and fainter, to
     measure honestly how faint a planet this data could reveal.
Nothing here claims a discovery: every planted object is labelled as simulated.
"""

import json
import warnings
from typing import Any

import numpy as np
from scipy.ndimage import binary_dilation
from scipy.ndimage import shift as nd_shift

from api.imaging.config import CACHE_DIR, PIXEL_SCALE_ARCSEC
from api.imaging.pipeline import RESPONSE_VERSION, _save_png, stretch
from api.imaging.track import aligned_track

STEP = 0.25  # px/day grid step: < 1 px drift error over a ~3-day window
VMAX = 3.0  # px/day (~18"/day): anything beyond ~200 AU at opposition, Pluto included
VMIN = 0.75  # px/day (~4.6"/day, ~770 AU): slower than ~2 px per window looks like a fixed star
STAR_SIGMA = 5.0  # fixed sources brighter than this in the time-median are masked out
CLIP_SIGMA = 5.0  # per-frame residual cap before stacking
DEMO_SIGMA = 1.5  # planted brightness for the demo pictures (the limit test goes fainter)
PSF_SIGMA = 0.8  # px; SPHEREx PSF FWHM ~1.9 px
REFLEX = 3548.0  # "/day: Earth's orbital speed seen from 1 AU away; rate ~ REFLEX / (D - 1)


def remove_static(zs: list[np.ndarray], dets: list[int]) -> np.ndarray:
    """Subtract each detector's own median sky: stars and their colours go, movers stay.

    Bright fixed stars still leave residue (their blur changes with wavelength), so they and a
    2 px border are masked to NaN. shortcut: a mover crossing a bright star is lost there.
    """
    z = np.nan_to_num(np.stack(zs))
    out = np.empty_like(z)
    dets_a = np.array(dets)
    for d in set(dets):
        m = dets_a == d
        out[m] = z[m] - np.median(z[m] if m.sum() >= 3 else z, axis=0)
    stars = binary_dilation(np.median(z, axis=0) > STAR_SIGMA, iterations=2)
    out[:, stars] = np.nan
    # one cosmic ray or hot pixel (hundreds of sigma, one frame) would outshine a mean stack;
    # a faint planet is ~1 sigma per frame, so capping at +-5 costs it nothing
    return np.clip(out, -CLIP_SIGMA, CLIP_SIGMA)


def stack(res: np.ndarray, dt: np.ndarray, vx: float, vy: float) -> np.ndarray:
    """Mean of frames shifted back along (vx, vy) px/day, in robust sigma units (NaN = masked)."""
    shifted = [
        nd_shift(r, (-vy * t, -vx * t), order=1, cval=np.nan) for r, t in zip(res, dt, strict=True)
    ]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = np.nanmean(shifted, axis=0)
    # next to a masked star only a few frames contribute: their mean is noisy and fakes peaks
    m[np.isfinite(shifted).sum(axis=0) < len(shifted) / 2] = np.nan
    ok = m[np.isfinite(m)]
    med = np.median(ok)
    return (m - med) / (1.4826 * np.median(np.abs(ok - med)))


def search(res: np.ndarray, dt: np.ndarray) -> list[tuple[float, float, float, int, int]]:
    """Best (snr, vx, vy, x, y) per trial motion, strongest first. x, y: position at dt = 0."""
    edge = int(np.ceil(VMAX * np.abs(dt).max())) + 2
    grid = np.arange(-VMAX, VMAX + STEP / 2, STEP)
    out = []
    for vx in grid:
        for vy in grid:
            if np.hypot(vx, vy) < VMIN:
                continue
            s = np.nan_to_num(stack(res, dt, vx, vy)[edge:-edge, edge:-edge], nan=-np.inf)
            y, x = np.unravel_index(np.argmax(s), s.shape)
            out.append((float(s[y, x]), float(vx), float(vy), int(x) + edge, int(y) + edge))
    return sorted(out, reverse=True)


def plant(
    res: np.ndarray, dt: np.ndarray, x0: float, y0: float, vx: float, vy: float, amp: float
) -> np.ndarray:
    """Add a moving point source of peak `amp` sigma per frame."""
    yy, xx = np.mgrid[: res.shape[1], : res.shape[2]]
    out = res.copy()
    for k, t in enumerate(dt):
        r2 = (xx - x0 - vx * t) ** 2 + (yy - y0 - vy * t) ** 2
        out[k] += amp * np.exp(-r2 / (2 * PSF_SIGMA**2))
    return out


def quiet_start(
    res: np.ndarray, dt: np.ndarray, vx: float, vy: float, avoid: tuple[float, float]
) -> tuple[float, float]:
    """A start spot whose whole track stays off masked stars and >= 8 px from Pluto."""
    n = res.shape[1]
    edge = int(np.ceil(VMAX * np.abs(dt).max())) + 3
    for y0 in np.linspace(edge, n - edge, 9):
        for x0 in np.linspace(edge, n - edge, 9):
            if np.hypot(x0 - avoid[0], y0 - avoid[1]) < 8:
                continue
            track = [(int(round(y0 + vy * t)), int(round(x0 + vx * t))) for t in dt]
            if all(np.isfinite(res[k, y, x]) for k, (y, x) in enumerate(track)):
                return float(x0), float(y0)
    raise RuntimeError("no star-free track in this field to plant a test planet")


def found(cands: list, x: float, y: float, vx: float, vy: float, floor: float) -> float | None:
    """SNR of the strongest candidate above `floor` that matches the truth, else None."""
    for snr, cvx, cvy, cx, cy in cands:
        if snr <= floor:
            return None
        if np.hypot(cx - x, cy - y) <= 1.5 and np.hypot(cvx - vx, cvy - vy) <= 2 * STEP:
            return snr
    return None


def build_planetx(body: str = "pluto", mjd: float = 60956.0, days: float = 2.0) -> dict[str, Any]:
    key = f"v{RESPONSE_VERSION}_planetx_{body}_{mjd:.2f}_{days:.2f}"
    cached = CACHE_DIR / "responses" / f"{key}.json"
    if cached.exists():
        return dict(json.loads(cached.read_text()))

    frames, zs, _, _, shape, _ = aligned_track(body, mjd, days, 0.1)
    n = shape[0]
    t = np.array([f["mjd"] for f in frames])
    dt = t - t.mean()
    res = remove_static(zs, [f["detector"] for f in frames])

    # 1. Blind search on the real data: does it find Pluto by itself?
    px = np.array([f["predicted"]["x"] for f in frames])
    py = np.array([f["predicted"]["y"] for f in frames])
    pvx, px0 = np.polyfit(dt, px, 1)
    pvy, py0 = np.polyfit(dt, py, 1)
    real = search(res, dt)
    best = real[0]
    pluto_found = np.hypot(best[3] - px0, best[4] - py0) <= 1.5
    # noise floor: strongest candidate that is not Pluto (anywhere, any motion)
    # Known objects are masked before hunting for new ones (as surveys remove known asteroids);
    # otherwise Pluto stacked at a wrong speed leaves ghosts that set a false noise floor.
    yy, xx = np.mgrid[:n, :n]
    clean = res.copy()
    for k in range(len(t)):
        clean[k][np.hypot(xx - px[k], yy - py[k]) <= 3] = np.nan
    floor = search(clean, dt)[0][0]  # strongest thing left: the noise floor, measured

    # 2. Plant "Planet X": ~300 AU at opposition, moving west, in a quiet corner, away from Pluto
    rate = REFLEX / 299 / PIXEL_SCALE_ARCSEC  # px/day
    vx, vy = rate, 0.0
    x0, y0 = quiet_start(res, dt, vx, vy, (px0, py0))
    pluto_peak = float(
        # from the unclipped frames: res is capped at CLIP_SIGMA
        np.nanmedian([zs[k][int(round(py[k])), int(round(px[k]))] for k in range(len(t))])
    )
    trials = []
    for amp in (3.0, 2.0, 1.5, 1.0, 0.7, 0.5, 0.35):
        snr = found(search(plant(clean, dt, x0, y0, vx, vy, amp), dt), x0, y0, vx, vy, floor)
        trials.append(
            {
                "amp_sigma": amp,
                "pluto_ratio": round(pluto_peak / amp, 1),
                "recovered": snr is not None,
                "stack_snr": round(snr, 1) if snr else None,
            }
        )
    faintest = min(
        (tr for tr in trials if tr["recovered"]), key=lambda tr: tr["amp_sigma"], default=None
    )

    # 3. Demo pictures at the faintest planet recovered: one frame, plain stack, shift-stack
    # pictures: faint enough to vanish in one frame, bright enough to read on a projector
    demo_amp = (
        DEMO_SIGMA
        if any(tr["recovered"] and tr["amp_sigma"] <= DEMO_SIGMA for tr in trials)
        else 3.0
    )
    demo = plant(clean, dt, x0, y0, vx, vy, demo_amp)
    k_mid = int(np.argmin(np.abs(dt)))
    pics = {
        "single": demo[k_mid] / (1.4826 * np.nanmedian(np.abs(demo[k_mid]))),
        "plain_stack": stack(demo, dt, 0.0, 0.0),
        "shift_stack": stack(demo, dt, vx, vy),
        "pluto_stack": stack(res, dt, best[1], best[2]),
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        urls = {k: _save_png(stretch(v, -2, 8), f"png/{key}/{k}.png") for k, v in pics.items()}

    resp = {
        "body": body,
        "window_days": round(float(t.max() - t.min()), 2),
        "n_frames": len(t),
        "size_px": n,
        "pluto": {
            "found_blind": bool(pluto_found),
            "snr": round(best[0], 1),
            "motion_arcsec_day": round(float(np.hypot(best[1], best[2])) * PIXEL_SCALE_ARCSEC, 1),
            "true_motion_arcsec_day": round(float(np.hypot(pvx, pvy)) * PIXEL_SCALE_ARCSEC, 1),
            "x": best[3],
            "y": best[4],
        },
        "noise_floor_snr": round(floor, 1),
        # share of the field hidden under masked bright stars: a planet there would be missed
        "masked_frac": round(float(np.isnan(res[0]).mean()), 2),
        "planet_x": {
            "simulated": True,
            "distance_au": 300,
            "motion_arcsec_day": round(rate * PIXEL_SCALE_ARCSEC, 1),
            "x": round(x0, 1),
            "y": round(y0, 1),
            "demo_amp_sigma": demo_amp,
        },
        "trials": trials,
        "faintest_recovered": faintest,
        "images": urls,
        "note": "Planet X here is simulated, planted into real SPHEREx frames to test the method.",
    }
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(resp))
    return resp
