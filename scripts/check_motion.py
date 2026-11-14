"""Science check: does Barnard's Star move by its known proper motion while field stars stay put?

Usage: python scripts/check_motion.py [RA DEC FOV]   (defaults: Barnard's Star, 2026 position)
Needs the cutouts cached (run warm_cache.py first) or network access.
"""

import sys
import warnings
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.imaging.config import PIXEL_SCALE_ARCSEC  # noqa: E402
from api.imaging.cutouts import get_cutouts  # noqa: E402
from api.imaging.pipeline import align, normalize, split_epochs, target_grid  # noqa: E402

PM_ARCSEC_YR = (-0.8028, 10.3625)  # Barnard's Star (pmRA*cos(dec), pmDec), Gaia DR3


def centroid(img: np.ndarray, y: int, x: int, r: int = 3) -> tuple[float, float]:
    box = np.nan_to_num(img[y - r : y + r + 1, x - r : x + r + 1]).clip(min=0)
    yy, xx = np.mgrid[-r : r + 1, -r : r + 1]
    return y + float((box * yy).sum() / box.sum()), x + float((box * xx).sum() / box.sum())


ra, dec, fov = (float(a) for a in sys.argv[1:4]) if len(sys.argv) > 3 else (269.4462, 4.7682, 0.1)
out_wcs, shape = target_grid(ra, dec, fov)
cuts = get_cutouts(ra, dec, fov)
mjd = np.array([c.mjd for c in cuts])
epochs = split_epochs(mjd)
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    zs = np.array([normalize(align(c.img, c.wcs, out_wcs, shape)) for c in cuts])
    stacks = {e: np.nanmedian(zs[epochs == e], axis=0) for e in sorted(set(epochs))}
t = {e: mjd[epochs == e].mean() for e in stacks}
first, last = min(stacks), max(stacks)

n = shape[0]
c0 = n // 2
yb, xb = np.unravel_index(np.nanargmax(stacks[first][c0 - 8 : c0 + 9, c0 - 8 : c0 + 9]), (17, 17))
target_px = (int(yb) + c0 - 8, int(xb) + c0 - 8)
masked = stacks[first].copy()
masked[target_px[0] - 6 : target_px[0] + 7, target_px[1] - 6 : target_px[1] + 7] = np.nan
masked[:5], masked[-5:], masked[:, :5], masked[:, -5:] = np.nan, np.nan, np.nan, np.nan
field_px = tuple(int(v) for v in np.unravel_index(np.nanargmax(masked), masked.shape))

dt = (t[last] - t[first]) / 365.25
print(f"{len(cuts)} frames, epochs {sorted(stacks)}, baseline {dt:.2f} yr")
for name, (y, x) in [("Barnard's Star", target_px), ("field star", field_px)]:
    y0, x0 = centroid(stacks[first], y, x)
    y1, x1 = centroid(stacks[last], y, x)
    # +x is west (cdelt1 < 0), so east motion = -dx
    east, north = -(x1 - x0) * PIXEL_SCALE_ARCSEC, (y1 - y0) * PIXEL_SCALE_ARCSEC
    px = np.hypot(east, north) / PIXEL_SCALE_ARCSEC
    print(f'{name:15s} measured  E {east:+6.2f}"  N {north:+6.2f}"  ({px:.2f} px)')
exp_e, exp_n = PM_ARCSEC_YR[0] * dt, PM_ARCSEC_YR[1] * dt
px = np.hypot(exp_e, exp_n) / PIXEL_SCALE_ARCSEC
print(f'{"expected":15s} Barnard\'s E {exp_e:+6.2f}"  N {exp_n:+6.2f}"  ({px:.2f} px); field 0')
