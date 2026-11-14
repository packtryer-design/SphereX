"""Measure which spectral bands from data/features.json actually show up in a spectrum.

Labels are only drawn as "seen" when the data backs them (>= 3 sigma), so the
front end never paints a molecule onto a spectrum that does not show it.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

FEATURES_PATH = Path(__file__).resolve().parents[2] / "data" / "features.json"
SEEN_SIGMA = 3.0
REF_BAND = (2.0, 2.3)  # um, continuum reference for "excess" bands
CLIP_MAD = 5.0
BLEND_NOTE = (
    "Another star sits inside the 12-arcsec aperture, so its light is mixed in. "
    "Treat short-wavelength bands with care; 6-arcsec pixels cannot split them."
)


@lru_cache(maxsize=1)
def load_features() -> dict:
    return json.loads(FEATURES_PATH.read_text(encoding="utf-8"))


def profile_for(target_id: str | None = None, kind: str | None = None) -> str | None:
    feats = load_features()
    if target_id and target_id in feats["targets"]:
        return feats["targets"][target_id]
    if kind and kind in feats["profiles"]:
        return kind
    return None


def _arrays(points: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    good = [
        p
        for p in points
        if p.get("flux") is not None
        and p.get("err") is not None
        and np.isfinite(p["flux"])
        and np.isfinite(p["err"])
        and p["err"] > 0
    ]
    good.sort(key=lambda p: p["wavelength_um"])
    wl = np.array([p["wavelength_um"] for p in good], float)
    fx = np.array([p["flux"] for p in good], float)
    er = np.array([p["err"] for p in good], float)
    return wl, fx, er


def _wmean(f: np.ndarray, e: np.ndarray) -> tuple[float, float]:
    """Inverse-variance mean after dropping points > CLIP_MAD robust sigmas from the median:
    one failed fit with a small error bar would otherwise outweigh dozens of good ones."""
    if f.size >= 5:
        med = np.median(f)
        mad = 1.4826 * np.median(np.abs(f - med))
        if mad > 0:
            keep = np.abs(f - med) <= CLIP_MAD * mad
            f, e = f[keep], e[keep]
    w = 1.0 / e**2
    return float(np.sum(w * f) / np.sum(w)), float(np.sqrt(1.0 / np.sum(w)))


def _band_contrast(wl, fx, er, lo, hi, side):
    """Return (contrast, sigma) where contrast = in-band / continuum - 1.

    Continuum = power law through weighted means of the two side windows.
    """
    inb = (wl >= lo) & (wl <= hi)
    for s in (side, 2 * side, 3 * side):  # widen across detector gaps
        left = (wl >= lo - s) & (wl < lo)
        right = (wl > hi) & (wl <= hi + s)
        if left.sum() >= 1 and right.sum() >= 1:
            break
    if inb.sum() < 1 or left.sum() < 1 or right.sum() < 1:
        return None
    fl, el = _wmean(fx[left], er[left])
    fr, er_ = _wmean(fx[right], er[right])
    xl, xr = wl[left].mean(), wl[right].mean()
    fin, ein = _wmean(fx[inb], er[inb])
    if fl <= 0 or fr <= 0:
        return None
    # power law through the side windows (straight in log-log): a smooth stellar
    # slope then gives zero contrast instead of a fake dip
    t = np.log(wl[inb].mean() / xl) / np.log(xr / xl)
    cont = fl ** (1 - t) * fr**t
    econt = cont * np.hypot((1 - t) * el / fl, t * er_ / fr)
    ratio = fin / cont
    sig = abs(ratio) * np.hypot(ein / fin if fin else np.inf, econt / cont)
    return ratio - 1.0, float(sig)


def _excess(wl, fx, er, lo, hi):
    """Flux above a Rayleigh-Jeans photosphere (F_nu ~ lambda^-2) pinned at 2.0-2.3 um.

    Returns (contrast, sigma, is_limit). If the reference band isn't detected (< 3 sigma,
    e.g. WISE 0855 once the neighbour star is fitted out), pin to its 3-sigma upper limit:
    the contrast is then a lower limit and sigma is how far the band sits above that.
    """
    ref = (wl >= REF_BAND[0]) & (wl <= REF_BAND[1])
    inb = (wl >= lo) & (wl <= hi)
    if ref.sum() < 1 or inb.sum() < 1:
        return None
    fref, eref = _wmean(fx[ref], er[ref])
    fin, ein = _wmean(fx[inb], er[inb])
    scale = (wl[inb].mean() / wl[ref].mean()) ** -2
    if fref < SEEN_SIGMA * eref:
        expected = (max(fref, 0.0) + SEEN_SIGMA * eref) * scale
        return fin / expected - 1.0, float(ein / expected), True
    expected = fref * scale
    ratio = fin / expected
    sig = abs(ratio) * np.hypot(ein / fin if fin else np.inf, eref / fref)
    return ratio - 1.0, float(sig), False


def measure(points: list[dict], profile: str) -> list[dict]:
    """Check every band of `profile` against `points` (API spectrum format)."""
    feats = load_features()
    prof = feats["profiles"][profile]
    side = feats.get("side_um", 0.08)
    wl, fx, er = _arrays(points)
    out = []
    for b in prof["bands"]:
        if b["type"] == "excess":
            res = _excess(wl, fx, er, b["lo"], b["hi"])
        else:
            res = _band_contrast(wl, fx, er, b["lo"], b["hi"], side)
        row = {
            "id": b["id"],
            "molecule": b["molecule"],
            "type": b["type"],
            "lo": b["lo"],
            "hi": b["hi"],
            "center_um": round((b["lo"] + b["hi"]) / 2, 3),
            "plain": b["plain"],
            "ref": feats["refs"][b["ref"]],
        }
        if res is None:
            covered = bool(((wl >= b["lo"]) & (wl <= b["hi"])).any())
            # covered but no positive continuum to compare against: source too faint there
            row.update(status="too_faint" if covered else "no_coverage", contrast=None, snr=None)
        else:
            contrast, sig, *limit = res
            if limit and limit[0]:
                row["lower_limit"] = True  # contrast is "at least": reference band undetected
            want = -1 if b["type"] == "absorption" else 1
            snr = abs(contrast) / sig if sig > 0 else 0.0
            if np.sign(contrast) == want and snr >= SEEN_SIGMA:
                status = "seen"
            elif np.sign(contrast) == -want and snr >= SEEN_SIGMA:
                status = "opposite"
            else:
                status = "not_clear"
            row.update(status=status, contrast=round(float(contrast), 3), snr=round(float(snr), 1))
        out.append(row)
    return out


def interpret(
    points: list[dict], target_id: str | None = None, kind: str | None = None, blended: bool = False
) -> dict | None:
    """Full payload for /api/spectrum's `features` field."""
    profile = profile_for(target_id, kind)
    if profile is None:
        return None
    prof = load_features()["profiles"][profile]
    bands = measure(points, profile)
    return {
        "profile": profile,
        "label": prof["label"],
        "plain": prof["plain"],
        "seen": sum(b["status"] == "seen" for b in bands),
        "bands": bands,
        "caveat": BLEND_NOTE if blended else None,
    }
