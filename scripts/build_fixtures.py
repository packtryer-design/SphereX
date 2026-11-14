"""Write FAKE fixture data that matches the API contract in docs/PLAN.md.

fixtures/frames.json   -> GET /api/frames  (8 synthetic PNGs: still stars + 1 mover)
fixtures/spectrum.json -> GET /api/spectrum (cold brown-dwarf-like shape)

Synthetic only, for building the UI before the real API works.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1] / "fixtures"
PNG = ROOT / "png"
N, SIZE = 8, 128
rng = np.random.default_rng(102)

stars = rng.uniform(5, SIZE - 5, size=(40, 2))
flux = rng.lognormal(0, 1, 40)
yy, xx = np.mgrid[0:SIZE, 0:SIZE]


def frame(i: int) -> np.ndarray:
    img = rng.normal(0, 0.05, (SIZE, SIZE))
    pts = list(zip(stars, flux, strict=True))
    pts.append((np.array([40 + i * 6.0, 64 + i * 2.0]), 3.0))  # the mover
    for (x, y), f in pts:
        img += f * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * 1.5**2))
    return np.arcsinh(img / 0.2)


def main() -> None:
    PNG.mkdir(parents=True, exist_ok=True)
    frames = []
    for i in range(N):
        name = f"fake_{i:02d}.png"
        plt.imsave(PNG / name, frame(i), cmap="gray", origin="lower", vmin=0, vmax=4)
        frames.append(
            {
                "png": f"/fixtures/png/{name}",
                "mjd": round(60800.0 + i * 91.3, 1),
                "epoch": i // 2 + 1,
                "detector": i % 6 + 1,
                "wavelength_um": round(0.75 + (i % 6) * 0.75 + 0.3, 2),
                "flagged_frac": round(float(rng.uniform(0, 0.05)), 3),
            }
        )
    (ROOT / "frames.json").write_text(
        json.dumps(
            {
                "_fake": True,
                "target": {"ra": 269.44627, "dec": 4.7682, "fov": 0.1},
                "frames": frames,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # Spectrum: cool-object continuum with water / methane dips, bright 4-5 um.
    wl = np.linspace(0.75, 5.0, 102)
    f = np.exp(-((wl - 1.25) ** 2) / 0.3) + 1.6 * np.exp(-((wl - 4.4) ** 2) / 0.25) + 0.05
    for c, d, w in [
        (1.4, 0.6, 0.06),
        (1.9, 0.6, 0.08),
        (1.65, 0.4, 0.05),
        (2.2, 0.4, 0.06),
        (3.3, 0.7, 0.1),
    ]:
        f *= 1 - d * np.exp(-((wl - c) ** 2) / (2 * w**2))
    f *= 0.01
    err = 0.05 * f + 0.0003
    noisy = f + rng.normal(0, err)
    pts = [
        {
            "wavelength_um": round(float(w), 4),
            "flux": round(float(v), 6),
            "err": round(float(e), 6),
            "epoch": 1,
        }
        for w, v, e in zip(wl, noisy, err, strict=True)
    ]
    (ROOT / "spectrum.json").write_text(
        json.dumps({"_fake": True, "unit": "mJy", "points": pts}, indent=2) + "\n", encoding="utf-8"
    )
    print("wrote", ROOT)


if __name__ == "__main__":
    main()
