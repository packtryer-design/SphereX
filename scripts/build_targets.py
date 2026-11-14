"""Build data/targets.json from SIMBAD (coords, proper motion, parallax).

Usage: python scripts/build_targets.py
Uses the Harvard SIMBAD mirror if the CDS server is down.
"""

import json
from pathlib import Path

import astropy.units as u
import requests
from astropy.coordinates import SkyCoord
from astropy.time import Time

MIRRORS = [
    "https://simbad.cds.unistra.fr/simbad/sim-tap/sync",
    "https://simbad.harvard.edu/simbad/sim-tap/sync",
]

# (slug, display name, SIMBAD identifier, kind, cutout fov in deg)
TARGETS = [
    ("barnards-star", "Barnard's Star", "Barnard's Star", "star", 0.1),
    ("eps-indi-b", "Epsilon Indi B", "eps Ind B", "brown_dwarf", 0.1),
    ("wise-0855", "WISE 0855-0714", "WISE J085510.83-071442.5", "brown_dwarf", 0.1),
    ("rw-aur", "RW Aurigae", "RW Aur", "star", 0.1),
    ("r-dra", "R Draconis", "R Dra", "star", 0.1),
]

# SPHEREx survey started 2025-05; mid-2026 sits between the first sweeps.
SURVEY_EPOCH = Time(2026.0, format="jyear")

QUERY = (
    "SELECT b.main_id, b.ra, b.dec, b.pmra, b.pmdec, b.plx_value, b.otype "
    "FROM basic AS b JOIN ident AS i ON b.oid = i.oidref WHERE i.id = '{}'"
)


def simbad(ident: str) -> dict | None:
    q = QUERY.format(ident.replace("'", "''"))
    for url in MIRRORS:
        try:
            r = requests.get(
                url,
                params={"request": "doQuery", "lang": "adql", "format": "json", "query": q},
                timeout=30,
            )
            if r.status_code != 200:
                continue
            j = r.json()
            if not j["data"]:
                return None
            cols = [m["name"] for m in j["metadata"]]
            return dict(zip(cols, j["data"][0], strict=True))
        except requests.RequestException:
            continue
    raise RuntimeError("all SIMBAD mirrors failed")


def propagate(row: dict) -> tuple[float, float]:
    """Move J2000 position to SURVEY_EPOCH using proper motion (parallax ignored)."""
    if row["pmra"] is None or row["pmdec"] is None:
        return row["ra"], row["dec"]
    c = SkyCoord(
        ra=row["ra"] * u.deg,
        dec=row["dec"] * u.deg,
        pm_ra_cosdec=row["pmra"] * u.mas / u.yr,
        pm_dec=row["pmdec"] * u.mas / u.yr,
        obstime=Time(2000.0, format="jyear"),
        frame="icrs",
    )
    n = c.apply_space_motion(new_obstime=SURVEY_EPOCH)
    return round(float(n.ra.deg), 7), round(float(n.dec.deg), 7)


def main() -> None:
    out = []
    for slug, name, ident, kind, fov in TARGETS:
        row = simbad(ident)
        if row is None:
            print("NOT FOUND:", ident)
            continue
        ra_now, dec_now = propagate(row)
        out.append(
            {
                "id": slug,
                "name": name,
                "simbad_id": row["main_id"],
                "kind": kind,
                "otype": row["otype"],
                "ra": row["ra"],
                "dec": row["dec"],
                "coord_epoch": "J2000",
                "pmra_mas_yr": row["pmra"],
                "pmdec_mas_yr": row["pmdec"],
                "plx_mas": row["plx_value"],
                "ra_2026": ra_now,
                "dec_2026": dec_now,
                "fov": fov,
            }
        )
        t = out[-1]
        shift = SkyCoord(t["ra"], t["dec"], unit="deg").separation(
            SkyCoord(ra_now, dec_now, unit="deg")
        )
        print(f"{slug:14s} J2000 {t['ra']:.5f} {t['dec']:.5f} -> 2026 {ra_now:.5f} {dec_now:.5f}"
              f"  moved {shift.arcsec:.0f} arcsec")

    out.append(
        {
            "id": "3i-atlas",
            "name": "Comet 3I/ATLAS",
            "simbad_id": None,
            "kind": "comet",
            "ra": None,
            "dec": None,
            "fov": 0.2,
            "note": "Moves fast: get its position per frame date from JPL Horizons. "
            "See https://irsa.ipac.caltech.edu/data/SPHEREx/docs/comet3iatlas/index.html",
        }
    )
    p = Path(__file__).resolve().parents[1] / "data" / "targets.json"
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps({"targets": out}, indent=2) + "\n", encoding="utf-8")
    print("wrote", p)


if __name__ == "__main__":
    main()
