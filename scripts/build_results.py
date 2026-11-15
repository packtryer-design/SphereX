"""Collect the "how we know it works" numbers into web/data/results.json.

Every number is measured from real SPHEREx frames and compared with an outside answer:
  - motion:  proper motion we measure vs Gaia / published values
  - pluto:   blind shift-and-stack find vs where NASA JPL Horizons puts Pluto
  - planet_x: faintest planted planet recovered, and what that means in AU
  - w2:      our 4.2-5.0 um flux vs AllWISE W2 (4.6 um)
  - labels:  which molecule labels the spectra actually show
Offline once the cutouts are cached (warm_cache.py). Takes a few minutes.

Usage:  python scripts/build_results.py
"""

import json
import sys
import warnings
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api.imaging.planetx import build_planetx  # noqa: E402
from api.science.motion import measure_motion  # noqa: E402
from api.science.spectrum import build_spectrum, load_targets  # noqa: E402

OUT = ROOT / "web" / "data" / "results.json"
MOTION_TARGETS = ["barnards-star", "eps-indi-b", "wise-0855", "rw-aur", "r-dra"]
SPECTRUM_TARGETS = ["barnards-star", "eps-indi-b", "wise-0855", "rw-aur", "r-dra"]

# Pluto during the search window (MJD 60957.5), from NASA JPL Horizons
PLUTO_R_AU, PLUTO_DELTA_AU, PLUTO_RADIUS_KM = 35.364, 35.094, 1188.0
PLANETS = {"Neptune-size": 24622.0, "Super-Earth (2x Earth)": 12742.0}


def reach_au(pluto_ratio: float, radius_km: float, darker: float = 1.0) -> int:
    """How far out a planet stays as bright as the faintest planted one we recovered.

    Reflected light ~ albedo * R^2 / (r^2 * Delta^2); at opposition Delta = r - 1.
    `darker`: how many times less reflective than Pluto the planet is.
    """
    target = (
        (radius_km / PLUTO_RADIUS_KM) ** 2
        / darker
        * pluto_ratio
        * (PLUTO_R_AU * PLUTO_DELTA_AU) ** 2
    )
    lo, hi = 2.0, 5000.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if (mid * (mid - 1)) ** 2 < target else (lo, mid)
    return int(round(lo, -1))


def main() -> None:
    warnings.simplefilter("ignore")
    targets = load_targets()

    motion = []
    for tid in MOTION_TARGETS:
        print(f"motion: {tid}", flush=True)
        r = measure_motion(tid)
        r.pop("epochs", None)
        motion.append(r)

    px = build_planetx()
    lim = px["faintest_recovered"]
    planet_x = {
        "frames": px["n_frames"],
        "window_days": px["window_days"],
        "faintest_recovered_sigma": lim["amp_sigma"],
        "times_fainter_than_pluto": lim["pluto_ratio"],
        "stack_snr": lim["stack_snr"],
        "masked_frac": px["masked_frac"],
        "reach": [
            {
                "planet": name,
                "au_same_reflectivity_as_pluto": reach_au(lim["pluto_ratio"], rad),
                "au_5x_darker": reach_au(lim["pluto_ratio"], rad, 5.0),
            }
            for name, rad in PLANETS.items()
        ],
        "assumption": (
            "Reflected sunlight scales as R^2 / (r^2 * Delta^2) at opposition; reflectivity "
            "as Pluto's, or 5x darker (methane-rich giants are dark in the near-infrared)."
        ),
    }

    w2, labels = [], []
    for tid in SPECTRUM_TARGETS:
        print(f"spectrum: {tid}", flush=True)
        t = targets[tid]
        s = build_spectrum(round(t["ra_2026"], 4), round(t["dec_2026"], 4), tid)
        w = s.get("w2_check")
        if w and w.get("ratio"):
            w2.append({"id": tid, "name": t.get("name", tid)} | w)
        bands = (s.get("features") or {}).get("bands", [])
        if bands:
            labels.append(
                {
                    "id": tid,
                    "name": t.get("name", tid),
                    "bands": [
                        {
                            "molecule": b["molecule"],
                            "center_um": b["center_um"],
                            "status": b["status"],
                        }
                        for b in bands
                    ],
                }
            )

    out = {
        "generated": datetime.now(UTC).strftime("%Y-%m-%d"),
        "motion": motion,
        "pluto": {
            "found_blind": px["pluto"]["found_blind"],
            "offset_arcsec": px["pluto"].get("offset_arcsec"),
            "snr": px["pluto"]["snr"],
            "frames": px["n_frames"],
        },
        "planet_x": planet_x,
        "w2": w2,
        "labels": labels,
    }
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
