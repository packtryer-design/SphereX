"""Build web/data/objects.json: the searchable catalog of objects Blink can open.

Only the names and the kind of object are written by hand below. Coordinates, SIMBAD
types, sizes and proper motions come from SIMBAD; visit dates come from IRSA. Nothing
is invented: a missing value stays missing.

Person C's science targets (data/targets.json) are added too, and for those the position
comes from targets.json (ra_2026/dec_2026), not SIMBAD. That keeps one set of coordinates
per object: the site, warm_cache.py and /api/spectrum then share one cache entry.

Usage:  python scripts/build_objects.py              # SIMBAD + SPHEREx visit summary
        python scripts/build_objects.py --no-visits  # SIMBAD only (fast)
"""

import json
import socket
import sys
from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord, get_constellation
from astropy.time import Time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "web" / "data" / "objects.json"
TARGETS = ROOT / "data" / "targets.json"
socket.setdefaulttimeout(60)  # a stalled IRSA/SIMBAD connection must not hang the build

SIMBAD_SERVERS = ["simbad.cds.unistra.fr", "simbad.harvard.edu"]
FOV_MIN, FOV_MAX = 0.1, 0.4  # degrees; bigger fields mean much slower first builds
EPOCH = 2026.5  # where fast-moving stars are centred (mid SPHEREx survey so far)
ABOUT = "Built by scripts/build_objects.py from SIMBAD and IRSA. Don't edit by hand."

# (id, display name, SIMBAD identifier, kind). Kinds are explained in web/js/kinds.js.
OBJECTS = [
    ("orion", "Orion Nebula", "M 42", "emission"),
    ("crab", "Crab Nebula", "M 1", "supernova_remnant"),
    ("lagoon", "Lagoon Nebula", "M 8", "emission"),
    ("eagle", "Eagle Nebula", "M 16", "emission"),
    ("omega", "Omega Nebula", "M 17", "emission"),
    ("trifid", "Trifid Nebula", "M 20", "emission"),
    ("dumbbell", "Dumbbell Nebula", "M 27", "planetary"),
    ("ring", "Ring Nebula", "M 57", "planetary"),
    ("owl", "Owl Nebula", "M 97", "planetary"),
    ("m78", "M78", "M 78", "reflection"),
    ("helix", "Helix Nebula", "NGC 7293", "planetary"),
    ("eskimo", "Eskimo Nebula", "NGC 2392", "planetary"),
    ("cats-eye", "Cat's Eye Nebula", "NGC 6543", "planetary"),
    ("saturn", "Saturn Nebula", "NGC 7009", "planetary"),
    ("ghost-of-jupiter", "Ghost of Jupiter", "NGC 3242", "planetary"),
    ("butterfly", "Butterfly Nebula", "NGC 6302", "planetary"),
    ("carina", "Carina Nebula", "NGC 3372", "emission"),
    ("tarantula", "Tarantula Nebula", "NGC 2070", "emission"),
    ("north-america", "North America Nebula", "NGC 7000", "emission"),
    ("pelican", "Pelican Nebula", "IC 5070", "emission"),
    ("elephants-trunk", "Elephant's Trunk region", "IC 1396", "emission"),
    ("rosette", "Rosette Nebula", "NGC 2237", "emission"),
    ("cocoon", "Cocoon Nebula", "IC 5146", "emission"),
    ("california", "California Nebula", "NGC 1499", "emission"),
    ("pacman", "Pacman Nebula", "NGC 281", "emission"),
    ("heart", "Heart Nebula", "IC 1805", "emission"),
    ("soul", "Soul Nebula", "IC 1848", "emission"),
    ("cone", "Cone Nebula region", "NGC 2264", "emission"),
    ("bubble", "Bubble Nebula", "NGC 7635", "emission"),
    ("lobster", "Lobster Nebula", "NGC 6357", "emission"),
    ("cats-paw", "Cat's Paw Nebula", "NGC 6334", "emission"),
    ("seagull", "Seagull Nebula", "IC 2177", "emission"),
    ("flaming-star", "Flaming Star Nebula", "IC 405", "emission"),
    ("crescent", "Crescent Nebula", "NGC 6888", "wind_bubble"),
    ("western-veil", "Western Veil Nebula", "NGC 6960", "supernova_remnant"),
    ("iris", "Iris Nebula", "NGC 7023", "reflection"),
    ("ngc1333", "NGC 1333", "NGC 1333", "reflection"),
    ("horsehead", "Horsehead Nebula", "Barnard 33", "dark"),
    # Not a nebula: a control object whose change over months is real and known.
    ("barnards-star", "Barnard's Star", "NAME Barnard's star", "moving_star"),
]

# Kind for each science profile in data/features.json, for targets not listed above.
PROFILE_KIND = {
    "brown_dwarf": "brown_dwarf",
    "young_star": "young_star",
    "mira": "variable_star",
    "m_dwarf": "moving_star",
}
TARGET_EPOCH = 2026.0  # data/targets.json gives positions for 2026.0


def science_targets() -> dict[str, dict]:
    """Person C's targets with a fixed position (the comet moves: it has none)."""
    if not TARGETS.exists():
        return {}
    data = json.loads(TARGETS.read_text(encoding="utf-8"))
    profiles = json.loads((ROOT / "data" / "features.json").read_text(encoding="utf-8"))
    out = {}
    for t in data["targets"]:
        if t.get("ra_2026") is None or t.get("dec_2026") is None:
            continue
        t["profile"] = profiles.get("targets", {}).get(t["id"])
        out[t["id"]] = t
    return out


def simbad_table(ids: list[str]):  # type: ignore[no-untyped-def]
    from astroquery.simbad import Simbad, conf

    for server in SIMBAD_SERVERS:
        conf.server = server
        try:
            s = Simbad()
            s.add_votable_fields("otype", "dim", "pmra", "pmdec", "ids")
            return s.query_objects(ids)
        except Exception as e:
            print(f"SIMBAD {server} failed: {e}", file=sys.stderr)
    raise SystemExit("No SIMBAD server reachable")


def num(v: object) -> float | None:
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if np.isnan(f) else f


def aliases(ids: str, keep: int = 6) -> list[str]:
    """Short catalog names (M, NGC, IC, Sh2, Barnard, common NAME) from SIMBAD's id list."""
    out = []
    for raw in str(ids).split("|"):
        name = " ".join(raw.split())
        if name.startswith("NAME "):
            out.append(name[5:])
        elif name.split(" ")[0] in {"M", "NGC", "IC", "Sh", "Sh2", "Barnard", "LBN", "Ced", "GJ"}:
            out.append(name)
    return list(dict.fromkeys(out))[:keep]


def visit_summary(ra: float, dec: float) -> dict[str, object] | None:
    from api.imaging.visits import list_visits

    try:
        v = list_visits(ra, dec)["visits"]
    except Exception as e:  # IRSA down or timed out: leave the count unknown, don't guess
        print(f"  visits unavailable for {ra}, {dec}: {e}", file=sys.stderr)
        return None
    if not v:
        return {"n": 0}
    iso = lambda mjd: Time(mjd, format="mjd").iso[:10]  # noqa: E731
    return {
        "n": len(v),
        "first": iso(v[0]["mjd_start"]),
        "last": iso(v[-1]["mjd_end"]),
        "full": sum(1 for x in v if x["full_coverage"]),
    }


def main() -> None:
    with_visits = "--no-visits" not in sys.argv
    science = science_targets()
    listed = {o[0] for o in OBJECTS}
    todo = list(OBJECTS) + [
        (t["id"], t["name"], t["simbad_id"], PROFILE_KIND.get(t["profile"], "moving_star"))
        for t in science.values()
        if t["id"] not in listed
    ]
    t = simbad_table([o[2] for o in todo])
    rows = {str(r["user_specified_id"]).strip(): r for r in t}
    objects = []
    for oid, name, sid, kind in todo:
        r = rows.get(sid)
        if r is None or num(r["ra"]) is None:
            print(f"skip {name}: not found in SIMBAD", file=sys.stderr)
            continue
        ra, dec = float(r["ra"]), float(r["dec"])
        pmra, pmdec = num(r["pmra"]), num(r["pmdec"])
        target = science.get(oid)
        if target:
            # One position per object: C's 2026 position, at full precision, so the cache
            # keys match warm_cache.py and /api/spectrum exactly.
            ra, dec = float(target["ra_2026"]), float(target["dec_2026"])
        elif kind == "moving_star" and pmra is not None and pmdec is not None:
            # SIMBAD positions are J2000; a fast star has moved arcminutes since then.
            yrs = EPOCH - 2000.0
            dec += pmdec / 3.6e6 * yrs
            ra += pmra / 3.6e6 * yrs / np.cos(np.radians(dec))
        size = num(r["galdim_majaxis"])  # arcmin
        fov = FOV_MIN if size is None else min(max(size * 1.2 / 60, FOV_MIN), FOV_MAX)
        o: dict[str, object] = {
            "id": oid,
            "name": name,
            "kind": kind,
            "simbad_id": " ".join(str(r["main_id"]).split()),
            "simbad_type": str(r["otype"]),
            "aliases": [a for a in aliases(r["ids"]) if a != name],
            "ra": ra if target else round(ra, 5),
            "dec": dec if target else round(dec, 5),
            "constellation": str(get_constellation(SkyCoord(ra, dec, unit="deg"))),
            "size_arcmin": None if size is None else round(size, 2),
            "fov": round(float(target.get("fov", FOV_MIN)) if target else fov, 3),
        }
        if target:
            o["target_id"] = oid  # /api/spectrum?target=<id>: PSF photometry + bands
            o["spectrum"] = "point"  # the site asks /api/spectrum, not /api/surface-spectrum
            o["profile"] = target["profile"]
            o["coord_epoch"] = TARGET_EPOCH
            o["pm_mas_yr"] = [target.get("pmra_mas_yr"), target.get("pmdec_mas_yr")]
        elif kind == "moving_star":
            o["coord_epoch"] = EPOCH
            o["pm_mas_yr"] = [pmra, pmdec]
        if with_visits:
            summary = visit_summary(round(ra, 4), round(dec, 4))
            if summary is not None:
                o["visits"] = summary
            print(f"{name}: {summary}", flush=True)
        objects.append(o)

    OUT.write_text(
        json.dumps(
            {
                "_about": ABOUT,
                "built": Time.now().iso[:10],
                "objects": objects,
            },
            indent=1,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(objects)} objects to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
