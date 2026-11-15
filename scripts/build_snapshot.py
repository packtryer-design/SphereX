"""Export SpotX's results for the demo objects as static files, so the site runs with no server.

The site is hosted on Netlify, which can't run the Python API. This calls the real API
in-process (same JSON as the live server) for each object, copies the images it refers to,
and writes everything under web/snapshot/. The front end reads those files whenever no live
API is reachable (see web/js/api.js).

It works offline from the local cache: nothing is downloaded from NASA. Anything not built
yet is skipped and listed, never half-exported. Warm objects first to include them:
    python scripts/warm_cache.py barnards-star wise-0855 orion
    python scripts/build_snapshot.py                     # default demo objects
    python scripts/build_snapshot.py ring helix          # add more, by catalog id
"""

import json
import shutil
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "web" / "snapshot"
DEFAULT_IDS = ["barnards-star", "wise-0855", "orion"]
PLUTO = {"body": "pluto", "mjd": 60956.0, "days": 2.0}
# Dates SPHEREx photographed each body (same as BODIES in web/track.html)
TRACKS = {"pluto": 60956.0, "neptune": 60849.0, "uranus": 60908.0}


def offline() -> None:
    """Never touch the network: use cached cutouts and frame lists only."""
    import api.imaging.cutouts as cutouts

    cutouts._download = lambda *a, **k: None  # missing cutout = skipped, not fetched


def main() -> None:
    offline()
    from api.imaging.config import CACHE_DIR
    from api.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    catalog = {
        o["id"]: o
        for o in json.loads((ROOT / "web/data/objects.json").read_text(encoding="utf-8"))["objects"]
    }
    ids = list(dict.fromkeys(DEFAULT_IDS + sys.argv[1:]))
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    def get(path: str, **q: Any) -> dict[str, Any] | None:
        r = client.get(f"/api/{path}?{urlencode({k: v for k, v in q.items() if v is not None})}")
        return r.json() if r.status_code == 200 else None

    def copy_png(url: str, folder: Path) -> str:
        """/cache/png/<key>/<name> -> snapshot/<folder>/<key>-<name>, path relative to web/."""
        rel = url.removeprefix("/cache/")
        src = CACHE_DIR / rel
        name = "-".join(Path(rel).parts[-2:])
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, folder / name)
        return (folder / name).relative_to(ROOT / "web").as_posix()

    def save(folder: Path, name: str, data: dict[str, Any]) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")

    index: dict[str, Any] = {"objects": {}, "pages": {}}
    skipped: list[str] = []
    for oid in ids:
        o = catalog.get(oid)
        if o is None:
            skipped.append(f"{oid}: not in the catalog")
            continue
        folder = OUT / oid
        pos = {"ra": o["ra"], "dec": o["dec"]}
        visits = get("visits", **pos)
        epoch = get("frames", **pos, fov=o["fov"], mode="epoch")
        if not visits or not epoch or not epoch["frames"]:
            skipped.append(f"{oid}: images not built locally")
            continue
        n_visits = len(visits["visits"])
        if len(epoch["frames"]) < n_visits and any(v["full_coverage"] for v in visits["visits"]):
            pass  # a visit at a detector edge has no image: that's real, not missing
        files = {"visits": "visits.json"}
        save(folder, "visits.json", visits)
        for f in epoch["frames"]:
            f["png"] = copy_png(f["png"], folder / "png")
        save(folder, "frames-epoch.json", epoch)
        files["epoch"] = "frames-epoch.json"
        rgb = get("frames", **pos, fov=o["fov"], mode="rgb")
        if rgb and rgb["frames"]:
            for f in rgb["frames"]:
                f["png"] = copy_png(f["png"], folder / "png")
            save(folder, "frames-rgb.json", rgb)
            files["rgb"] = "frames-rgb.json"
        # Difference against every visit, so any A/B pair works in the demo.
        for e in sorted({f["epoch"] for f in epoch["frames"]}):
            d = get("frames", **pos, fov=o["fov"], mode="diff", ref=None if e == 1 else e)
            if d and d["frames"]:
                for f in d["frames"]:
                    f["png"] = copy_png(f["png"], folder / "png")
                save(folder, f"frames-diff-ref{e}.json", d)
                files[f"diff{e}"] = f"frames-diff-ref{e}.json"
        if o.get("spectrum") == "point" or o.get("target_id"):
            s = get("spectrum", **pos, target=o.get("target_id") or oid)
            kind = "point"
            if s and s.get("binned") and not s.get("w2_check"):
                # The cached spectrum was saved while AllWISE was unreachable: try the
                # WISE cross-check again (one quick catalog query; None if still down).
                from api.science.spectrum import load_targets, w2_check

                s["w2_check"] = w2_check(o["ra"], o["dec"], s["binned"], load_targets().get(oid))
        else:
            s = get("surface-spectrum", **pos, field_ra=o["ra"], field_dec=o["dec"], fov=o["fov"])
            kind = "surface"
        if s and s.get("points"):
            save(folder, f"spectrum-{kind}.json", s)
            files["spectrum"] = f"spectrum-{kind}.json"
        # "Is this new?" marks (Known objects button). These query Gaia/CatWISE and SkyBoT unless
        # cached; a service that's down just leaves that layer out of the demo.
        for kind in ("ghosts", "asteroids"):
            k = get(kind, **pos, fov=o["fov"])
            if k is None:
                skipped.append(f"{oid}: {kind} unavailable (catalog service down?)")
                continue
            save(folder, f"{kind}.json", k)
            files[kind] = f"{kind}.json"
        index["objects"][oid] = {"ra": o["ra"], "dec": o["dec"], "fov": o["fov"], "files": files}
        size = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) / 1e6
        print(f"{oid}: {', '.join(files)} ({size:.1f} MB)", flush=True)

    # The Planet X page (track.html)
    for body, mjd in TRACKS.items():
        folder = OUT / body
        track = get("track", body=body, mjd=mjd, days=2.0, fov=0.1)
        if track and track.get("frames"):
            for f in track["frames"]:
                f["png"] = copy_png(f["png"], folder / "png")
            save(folder, "track.json", track)
            index["pages"][f"track:{body}"] = f"snapshot/{body}/track.json"
        else:
            skipped.append(f"Planet X page: {body} track not built locally")
    folder = OUT / "pluto"
    planetx = get("planetx", **PLUTO)
    if planetx and planetx.get("images"):
        for k, v in planetx["images"].items():
            if isinstance(v, str) and v.startswith("/cache/"):
                planetx["images"][k] = copy_png(v, folder / "png")
        save(folder, "planetx.json", planetx)
        index["pages"]["planetx"] = "snapshot/pluto/planetx.json"
    else:
        skipped.append("Planet X page: planet search not built locally")

    from datetime import datetime, timezone

    index["built"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (OUT / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file()) / 1e6
    n_obj, n_pages = len(index["objects"]), len(index["pages"])
    print(f"\nwrote web/snapshot/: {n_obj} objects, {n_pages} page files, {total:.1f} MB")
    for s in skipped:
        print("  skipped:", s)


if __name__ == "__main__":
    main()
