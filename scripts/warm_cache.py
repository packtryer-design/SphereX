"""Pre-build every mode for the demo targets so the live demo never waits on IRSA.

Usage:  python scripts/warm_cache.py                 # all targets in data/targets.json
        python scripts/warm_cache.py RA DEC [FOV]    # one position
"""

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.imaging.pipeline import MODES, build_frames  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

if len(sys.argv) >= 3:
    fov = float(sys.argv[3]) if len(sys.argv) > 3 else 0.1
    targets = [{"name": "cli", "ra": float(sys.argv[1]), "dec": float(sys.argv[2]), "fov": fov}]
else:
    raw = json.loads(Path("data/targets.json").read_text())["targets"]
    # current-epoch positions: J2000 "ra"/"dec" put fast movers like Barnard's Star off-centre
    targets = [t | {"ra": t["ra_2026"], "dec": t["dec_2026"]} for t in raw if t.get("ra_2026")]
    for t in raw:
        if not t.get("ra_2026"):  # e.g. comets: no fixed position, needs per-frame ephemeris
            logging.warning("skipping %s: no fixed 2026 position", t["name"])

for t in targets:
    for mode in MODES:
        t0 = time.time()
        r = build_frames(t["ra"], t["dec"], t.get("fov", 0.1), mode)
        logging.info(
            "%s %s: %d frames in %.0fs", t["name"], mode, len(r["frames"]), time.time() - t0
        )
