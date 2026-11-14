"""Copy finished results for the demo objects from cache/ into cache/demo/ (committed to git).

The server copies cache/demo/ into its cache at startup, so a fresh deploy opens the demo
objects instantly and keeps working if IRSA is down. Only small results are copied: API
responses, PNGs, spectra, frame lists and catalog lookups, not the raw cutouts.

Usage:  python scripts/demo_snapshot.py                  # all of data/targets.json + orion
        python scripts/demo_snapshot.py barnards-star orion
Run warm_cache.py first; objects that aren't warm yet are reported and skipped.
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api.imaging.config import CACHE_DIR, DEMO_DIR  # noqa: E402
from api.imaging.pipeline import RESPONSE_VERSION  # noqa: E402

SKIP = {"cutouts", "epsf", "demo"}  # raw downloads are far too big for git
DEFAULT_EXTRA = ["orion"]


def current(p: Path) -> bool:
    """Image results from an older pipeline version are never read again: don't ship them."""
    if p.parent.name in ("responses", "png"):
        return p.name.startswith(f"v{RESPONSE_VERSION}_")
    return True


def positions(ids: list[str]) -> dict[str, list[tuple[float, float]]]:
    """Every position an id is served at: the catalog's and data/targets.json's can differ."""
    out: dict[str, list[tuple[float, float]]] = {i: [] for i in ids}
    catalog = json.loads((ROOT / "web" / "data" / "objects.json").read_text(encoding="utf-8"))
    for o in catalog["objects"]:
        if o["id"] in out:
            out[o["id"]].append((o["ra"], o["dec"]))
    for t in json.loads((ROOT / "data" / "targets.json").read_text(encoding="utf-8"))["targets"]:
        if t["id"] in out and t.get("ra_2026") is not None:
            out[t["id"]].append((t["ra_2026"], t["dec_2026"]))
    return out


def main() -> None:
    ids = sys.argv[1:]
    if not ids:
        targets = json.loads((ROOT / "data" / "targets.json").read_text(encoding="utf-8"))
        ids = [t["id"] for t in targets["targets"] if t.get("ra_2026") is not None]
        ids += DEFAULT_EXTRA
    cache, demo = CACHE_DIR.resolve(), DEMO_DIR.resolve()
    entries = [p for p in cache.iterdir() if p.is_dir() and p.name not in SKIP]
    total = 0
    for oid, pos in positions(ids).items():
        if not pos:
            print(f"{oid}: unknown id")
            continue
        # every cache file name for a position contains its rounded "RA_+Dec"
        tags = {f"{round(ra, 4):.4f}_{round(dec, 4):+.4f}" for ra, dec in pos}
        found = [
            p for d in entries for p in d.iterdir() if any(t in p.name for t in tags) and current(p)
        ]
        has_images = any(p.parent.name == "responses" for p in found)
        for src in found:
            dst = demo / src.relative_to(cache)
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        size = sum(f.stat().st_size for p in found for f in ([p] if p.is_file() else p.rglob("*")))
        total += size
        note = "" if has_images else "  <- no image responses yet: run warm_cache.py first"
        print(f"{oid}: {len(found)} entries, {size / 1e6:.1f} MB{note}")
    print(f"total {total / 1e6:.1f} MB in {demo}")


if __name__ == "__main__":
    main()
