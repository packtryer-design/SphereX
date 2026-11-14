"""Pre-build images for the catalog, plus spectra for the science targets, so the live demo
never waits on IRSA.

Usage:  python scripts/warm_cache.py                 # web/data/objects.json + data/targets.json
        python scripts/warm_cache.py orion wise-0855 # just these ids (from either list)
        python scripts/warm_cache.py RA DEC [FOV]    # one position
"""

import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api.imaging.pipeline import build_frames  # noqa: E402
from api.science.spectrum import build_spectrum  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

MODES = ("epoch", "diff", "rgb")  # what the front end asks for; "single" is per-exposure


def is_number(s: str) -> bool:
    try:
        float(s)
    except ValueError:
        return False
    return True


args = sys.argv[1:]
if len(args) >= 2 and is_number(args[0]) and is_number(args[1]):
    fov = float(args[2]) if len(args) > 2 else 0.1
    targets = [{"name": "cli", "ra": float(args[0]), "dec": float(args[1]), "fov": fov}]
else:
    catalog = json.loads((ROOT / "web" / "data" / "objects.json").read_text(encoding="utf-8"))
    everything = [o for o in catalog["objects"] if o.get("visits", {}).get("n", 1) > 0]
    science = ROOT / "data" / "targets.json"  # Person C's demo targets, at 2026 positions
    if science.exists():
        for t in json.loads(science.read_text(encoding="utf-8"))["targets"]:
            # `or`, not get(..., default): the keys exist but are null for the comet
            ra, dec = t.get("ra_2026") or t["ra"], t.get("dec_2026") or t["dec"]
            if ra is None:  # 3I/ATLAS moves: needs per-frame JPL Horizons positions
                logging.warning("skipping %s: no fixed position", t["name"])
                continue
            known = next((o for o in everything if o["id"] == t["id"]), None)
            if known is not None:  # same object in the catalog: one position, one warm
                known.update(ra=ra, dec=dec, spectrum=True)
                continue
            everything.append(
                {
                    "id": t["id"],
                    "name": t["name"],
                    "ra": ra,
                    "dec": dec,
                    "fov": t.get("fov", 0.1),
                    "spectrum": True,  # /api/spectrum serves these: warm it too
                }
            )
    targets = [o for o in everything if not args or o["id"] in args]

for t in targets:
    for mode in MODES:
        t0 = time.time()
        try:
            r = build_frames(t["ra"], t["dec"], t.get("fov", 0.1), mode)
        except RuntimeError as e:
            logging.warning("%s %s: %s", t["name"], mode, e)
            continue
        logging.info(
            "%s %s: %d frames in %.0fs", t["name"], mode, len(r["frames"]), time.time() - t0
        )
    if t.get("spectrum"):
        # The spectrum uses its own smaller cutouts (SPEC_FOV), which still weigh ~4 MB each
        # because of the EPSF table: a cold spectrum on stage would mean ~350 slow downloads.
        t0 = time.time()
        try:
            s = build_spectrum(t["ra"], t["dec"], t["id"])
        except Exception as e:  # Gaia/IRSA down: keep warming the rest
            logging.warning("%s spectrum: %s", t["name"], e)
            continue
        logging.info(
            "%s spectrum: %d points in %.0fs", t["name"], len(s["points"]), time.time() - t0
        )
