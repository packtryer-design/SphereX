"""Science check for a tracked body: is the thing at the predicted spot really the mover?

1. Centroid near the JPL Horizons prediction in every frame -> residual in pixels.
2. Static-star test: brightness at frame A's predicted spot in frames where the body had moved
   >= 3 px away. A background star stays bright there; a moving body leaves.

Usage: python scripts/check_track.py [body mjd days fov]   (default: pluto 60956 2 0.1)
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.imaging.config import CACHE_DIR  # noqa: E402
from api.imaging.track import build_track  # noqa: E402

BOX = 3  # half-width of the centroid box, px


def img(f: dict) -> np.ndarray:
    a = np.asarray(Image.open(CACHE_DIR / f["png"][len("/cache/") :]), float)
    return a[::-1]  # back to FITS row order, so predicted (x, y) index it directly


def centroid(a: np.ndarray, x: float, y: float) -> tuple[float, float, float]:
    ix, iy = int(round(x)), int(round(y))
    box = a[iy - BOX : iy + BOX + 1, ix - BOX : ix + BOX + 1]
    w = (box - np.median(a)).clip(min=0)
    yy, xx = np.mgrid[-BOX : BOX + 1, -BOX : BOX + 1]
    s = w.sum()
    return (ix + (w * xx).sum() / s, iy + (w * yy).sum() / s, float(box.max())) if s else (x, y, 0)


body, mjd, days, fov = sys.argv[1:5] if len(sys.argv) > 4 else ("pluto", 60956, 2, 0.1)
r = build_track(body, float(mjd), float(days), float(fov))
frames = r["frames"]
ims = [img(f) for f in frames]
bg = np.array([np.median(a) for a in ims])

res, peak = [], []
for f, a in zip(frames, ims, strict=True):
    p = f["predicted"]
    cx, cy, pk = centroid(a, p["x"], p["y"])
    res.append(np.hypot(cx - p["x"], cy - p["y"]))
    peak.append(pk)
res, peak = np.array(res), np.array(peak) - bg
noise = np.array([1.4826 * np.median(np.abs(a - np.median(a))) for a in ims])  # robust sigma
seen = peak > 5 * noise

# static-star test: same pixel, frames where the body is >= 3 px away
here, away = [], []
for i, f in enumerate(frames):
    if not seen[i]:
        continue
    p = f["predicted"]
    for j, g in enumerate(frames):
        q = g["predicted"]
        if np.hypot(q["x"] - p["x"], q["y"] - p["y"]) >= 3:
            v = ims[j][int(round(p["y"])), int(round(p["x"]))] - bg[j]
            away.append(v)
    here.append(ims[i][int(round(p["y"])), int(round(p["x"]))] - bg[i])

print(f"{r['name']}: {len(frames)} frames, body visible in {int(seen.sum())}")
print(f"position residual vs Horizons (visible frames): median {np.median(res[seen]):.2f} px")
print(
    f"brightness at the body's spot: {np.median(here):.1f} when it's there, "
    f"{np.median(away):.1f} after it has moved >= 3 px (a background star would stay bright)"
)
