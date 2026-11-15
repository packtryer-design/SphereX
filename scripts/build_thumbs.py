"""Download one small infrared preview per catalog object into web/data/thumbs/<id>.jpg.

The previews are unWISE (NASA WISE, 3.4 + 4.6 µm) cutouts from the Legacy Survey viewer:
the same patch of sky as the object's field, so the home page shows real sky, not stock
art. Saved into the repo so the site never waits on (or breaks with) an outside server.

Usage:  python scripts/build_thumbs.py          # only missing previews
        python scripts/build_thumbs.py --force  # all of them again
"""

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "data" / "thumbs"
URL = "https://www.legacysurvey.org/viewer/cutout.jpg"
W, H = 320, 200
EXTRA = {"pluto-field": (304.13338, -23.61816, 0.1)}  # the Planet X page (2025-10-01 field)


def main() -> None:
    force = "--force" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((ROOT / "web" / "data" / "objects.json").read_text(encoding="utf-8"))
    fields = {o["id"]: (o["ra"], o["dec"], o.get("fov", 0.1)) for o in catalog["objects"]}
    fields.update(EXTRA)
    with httpx.Client(timeout=60, follow_redirects=True) as http:
        for oid, (ra, dec, fov) in fields.items():
            path = OUT / f"{oid}.jpg"
            if path.exists() and not force:
                continue
            # Show a bit more than the SPHEREx field so small objects still have context.
            pixscale = max(fov, 0.1) * 1.4 * 3600 / W
            params: dict[str, str | float | int] = {
                "ra": ra,
                "dec": dec,
                "layer": "unwise-neo7",
                "pixscale": round(pixscale, 2),
                "width": W,
                "height": H,
            }
            try:
                r = http.get(URL, params=params)
                r.raise_for_status()
            except httpx.HTTPError as e:  # leave it missing: the card just shows no picture
                print(f"{oid}: failed ({e})", file=sys.stderr)
                continue
            if not r.headers.get("content-type", "").startswith("image/"):
                print(f"{oid}: not an image", file=sys.stderr)
                continue
            path.write_bytes(r.content)
            print(f"{oid}: {len(r.content) // 1024} KB", flush=True)


if __name__ == "__main__":
    main()
