"""Turn cutouts into aligned, consistently stretched PNG frames for the flipbook."""

import json
import warnings
from collections import defaultdict
from typing import Any

import numpy as np
from astropy.stats import sigma_clipped_stats
from astropy.visualization import AsinhStretch
from astropy.wcs import WCS
from PIL import Image
from reproject import reproject_interp

from api.imaging.config import CACHE_DIR, EPOCH_GAP_DAYS, MAX_EPOCH_DAYS, PIXEL_SCALE_ARCSEC
from api.imaging.cutouts import Cutout, fetch_cutouts

MODES = ("single", "epoch", "rgb", "diff")
RESPONSE_VERSION = 2  # bump when the response shape changes, so old cached JSON is ignored


def target_grid(
    ra: float, dec: float, fov: float, scale: float = PIXEL_SCALE_ARCSEC
) -> tuple[WCS, tuple[int, int]]:
    n = int(np.ceil(fov * 3600 / scale)) | 1  # odd size: the target lands on the centre pixel
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [(n + 1) / 2] * 2
    w.wcs.cdelt = [-scale / 3600, scale / 3600]  # north up, east left
    return w, (n, n)


def align(img: np.ndarray, wcs: WCS, out_wcs: WCS, shape: tuple[int, int]) -> np.ndarray:
    out, _ = reproject_interp((img, wcs), out_wcs, shape_out=shape)
    return out


def normalize(a: np.ndarray) -> np.ndarray:
    """Background-subtracted, in units of the background noise (sigma)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # NaNs (masked pixels, frame edges) are expected
        _, med, std = sigma_clipped_stats(a, sigma=3)
    return (a - med) / std


def split_epochs(mjd: np.ndarray) -> np.ndarray:
    """1-based epoch per frame: a new epoch after each long gap; over-long epochs are chunked."""
    order = np.argsort(mjd)
    t = mjd[order]
    group = np.concatenate([[0], np.cumsum(np.diff(t) > EPOCH_GAP_DAYS)])
    labels = np.empty(len(t), dtype=float)
    for g in np.unique(group):
        m = group == g
        span = t[m] - t[m][0]
        sub = span // (MAX_EPOCH_DAYS / 2) if span[-1] > MAX_EPOCH_DAYS else np.zeros(m.sum())
        labels[m] = g * 1000 + sub
    epochs = np.empty(len(t), dtype=int)
    epochs[order] = np.unique(labels, return_inverse=True)[1] + 1
    return epochs


def stretch(z: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
    x = np.clip((z - vmin) / (vmax - vmin), 0, 1)
    return np.nan_to_num(AsinhStretch(0.1)(x), nan=0.0)


def make_rgb(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.dstack([r, g, b])


def _save_png(x: np.ndarray, path: str) -> str:
    full = CACHE_DIR / path
    full.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((x * 255).astype(np.uint8)[::-1]).save(full)  # FITS rows run bottom-up
    return f"/cache/{path}"


def _wavelength_at(c: Cutout, ra: float, dec: float) -> float | None:
    x, y = c.wcs.all_world2pix(ra, dec, 0)
    ix, iy = int(round(float(x))), int(round(float(y)))
    if 0 <= iy < c.wave.shape[0] and 0 <= ix < c.wave.shape[1]:
        return round(float(c.wave[iy, ix]), 4)
    return None


def build_frames(
    ra: float,
    dec: float,
    fov: float,
    mode: str = "single",
    detector: str = "all",
    ref: int | None = None,
) -> dict[str, Any]:
    """`ref` (diff mode only): the epoch every other epoch is compared against. Default: first."""
    ra, dec, fov = round(ra, 4), round(dec, 4), round(fov, 3)
    ref = ref if mode == "diff" and ref != 1 else None  # epoch 1 is the default reference
    key = f"v{RESPONSE_VERSION}_{ra:.4f}_{dec:+.4f}_{fov:.3f}_{mode}_{detector}"
    if ref is not None:
        key += f"_ref{ref}"
    cached = CACHE_DIR / "responses" / f"{key}.json"
    if cached.exists():
        return dict(json.loads(cached.read_text()))

    out_wcs, shape = target_grid(ra, dec, fov)
    frames: list[dict[str, Any]] = []
    zs: list[np.ndarray] = []
    cuts, failed = fetch_cutouts(ra, dec, fov)
    for c in cuts:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # all-NaN slices, SIP notices
            a = align(c.img, c.wcs, out_wcs, shape)
        nan_frac = float(np.isnan(a).mean())
        if nan_frac > 0.5:  # target sat at the detector edge
            continue
        zs.append(normalize(a))
        frames.append(
            {
                "mjd": round(c.mjd, 4),
                "detector": c.detector,
                "wavelength_um": _wavelength_at(c, ra, dec),
                "n_frames": 1,
                "flagged_frac": round(nan_frac, 3),
            }
        )
    if not frames:
        return {"target": {"ra": ra, "dec": dec, "fov": fov}, "frames": []}

    order = np.argsort([f["mjd"] for f in frames])
    frames = [frames[i] for i in order]
    zs = [zs[i] for i in order]
    epochs = split_epochs(np.array([f["mjd"] for f in frames]))
    for f, e in zip(frames, epochs, strict=True):
        f["epoch"] = int(e)

    if mode == "single":
        if detector != "all":
            keep = [i for i, f in enumerate(frames) if f["detector"] == int(detector)]
            frames, zs = [frames[i] for i in keep], [zs[i] for i in keep]
        images, out = zs, frames
    else:
        images, out = _combine(frames, zs, mode, detector, ref)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        vmax = float(np.nanpercentile(np.stack(images), 99.5)) if images else 1.0
    for i, (img, f) in enumerate(zip(images, out, strict=True)):
        if mode == "rgb":
            x = make_rgb(*(stretch(ch, -2, vmax) for ch in img))
        elif mode == "diff":
            x = np.clip(np.nan_to_num(img) / 10 + 0.5, 0, 1)  # mid-grey = no change, +-5 sigma
        else:
            x = stretch(img, -2, vmax)
        f["png"] = _save_png(x, f"png/{key}/{i:03d}.png")

    resp = {"target": {"ra": ra, "dec": dec, "fov": fov}, "frames": out}
    if not failed:  # a partial result must not be frozen in the cache
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(resp))
    return resp


def _combine(
    frames: list[dict[str, Any]],
    zs: list[np.ndarray],
    mode: str,
    detector: str,
    ref: int | None = None,
) -> tuple[list[Any], list[dict[str, Any]]]:
    groups: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, f in enumerate(frames):
        groups[(f["epoch"], f["detector"])].append(i)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # median per (epoch, detector): ~17 frames each, rejects cosmic rays
        stack = {k: np.nanmedian([zs[i] for i in idx], axis=0) for k, idx in groups.items()}
    epochs = sorted({e for e, _ in stack})
    dets = sorted({d for _, d in stack}) if detector == "all" else [int(detector)]

    def meta(e: int, use: list[int] | None = None) -> dict[str, Any]:
        used = [d for d in (use if use is not None else dets) if (e, d) in groups]
        idx = [i for d in used for i in groups[(e, d)]]
        waves = [frames[i]["wavelength_um"] for i in idx if frames[i]["wavelength_um"]]
        mjds = [frames[i]["mjd"] for i in idx]
        return {
            "mjd": round(float(np.mean(mjds)), 4),
            "mjd_start": round(float(min(mjds)), 4),
            "mjd_end": round(float(max(mjds)), 4),
            # Which detectors (wavelength ranges) went into this image. Epochs with different
            # detectors are not like-for-like: differences may be colour, not change.
            "detectors": used,
            "epoch": e,
            "detector": None if detector == "all" else int(detector),
            "wavelength_um": None if detector == "all" or not waves else float(np.median(waves)),
            "n_frames": len(idx),
            "flagged_frac": round(float(np.mean([frames[i]["flagged_frac"] for i in idx])), 3),
        }

    def epoch_image(e: int) -> np.ndarray:
        # mean, not median, across detectors: a brown dwarf bright in only D5-D6 must survive
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return np.nanmean([stack[(e, d)] for d in dets if (e, d) in stack], axis=0)

    have = [e for e in epochs if any((e, d) in stack for d in dets)]
    if mode == "epoch":
        return [epoch_image(e) for e in have], [meta(e) for e in have]
    if mode == "rgb":
        if len(have) < 2:
            return [], []
        pick = (
            [have[0], have[len(have) // 2], have[-1]] if len(have) > 2 else [have[0], *have[1:] * 2]
        )
        m = meta(pick[-1]) | {
            "epoch": None,
            "epochs": pick,  # red, green, blue
            "n_frames": sum(meta(e)["n_frames"] for e in pick),
        }
        return [[epoch_image(e) for e in pick]], [m]
    # diff: per detector first, and only detectors both epochs have, so wavelength differences
    # cancel instead of showing up as fake "change"
    base = ref if ref in have else have[0] if have else None
    images, out = [], []
    for e in have:
        if e == base:
            continue
        shared = [d for d in dets if (e, d) in stack and (base, d) in stack]
        if shared:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                images.append(
                    np.nanmean([stack[(e, d)] - stack[(base, d)] for d in shared], axis=0)
                )
            out.append(meta(e, shared) | {"ref_epoch": base})
    return images, out
