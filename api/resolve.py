"""Turn an object name ("Helix Nebula", "NGC 7293") into coordinates.

Used by the search box for anything not in the built-in catalog. Tries SIMBAD (the
CDS server, then its Harvard mirror), then NED, which knows fewer nebula nicknames.
Found names are cached on disk, so each is looked up once.
"""

import json
import logging
import re
from typing import Any

import httpx
from astropy.coordinates import SkyCoord, get_constellation

from api.imaging.config import CACHE_DIR

log = logging.getLogger(__name__)

SIMBAD_SERVERS = ["simbad.cds.unistra.fr", "simbad.harvard.edu"]
NED_LOOKUP = "https://ned.ipac.caltech.edu/srs/ObjectLookup"


def _simbad(name: str) -> dict[str, Any] | None:
    from astroquery.simbad import Simbad, conf

    for server in SIMBAD_SERVERS:
        conf.server = server
        try:
            s = Simbad()
            s.add_votable_fields("otype")
            t = s.query_object(name)
        except Exception as e:  # server down: try the next one
            log.info("SIMBAD %s failed: %s", server, e)
            continue
        if t is None or len(t) == 0:
            return None  # the service answered: no such object
        r = t[0]
        return {
            "catalog_name": " ".join(str(r["main_id"]).split()),
            "ra": float(r["ra"]),
            "dec": float(r["dec"]),
            "type": str(r["otype"]),
            "source": "SIMBAD",
        }
    raise httpx.ConnectError("no SIMBAD server reachable")


def _ned(name: str) -> dict[str, Any] | None:
    r = httpx.post(NED_LOOKUP, data={"json": json.dumps({"name": {"v": name}})}, timeout=20)
    r.raise_for_status()
    pref = r.json().get("Preferred") or {}
    pos = pref.get("Position") or {}
    if pos.get("RA") is None or pos.get("Dec") is None:
        return None
    return {
        "catalog_name": pref.get("Name"),
        "ra": float(pos["RA"]),
        "dec": float(pos["Dec"]),
        "type": (pref.get("ObjType") or {}).get("Value"),
        "source": "NED",
    }


def resolve(name: str) -> dict[str, Any] | None:
    """Coordinates for `name`, or None if no service knows it.

    Raises httpx.HTTPError only when every service was unreachable."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    path = CACHE_DIR / "names" / f"{slug}.json"
    if path.exists():
        return json.loads(path.read_text())

    errors = 0
    found = None
    for lookup in (_simbad, _ned):
        try:
            found = lookup(name)
        except httpx.HTTPError as e:
            log.info("%s failed: %s", lookup.__name__, e)
            errors += 1
            continue
        if found:
            break
    if found is None:
        if errors == 2:
            raise httpx.ConnectError("name lookup services unreachable")
        return None  # not cached: a later lookup may succeed once catalogs update

    found["name"] = name.strip()
    found["ra"], found["dec"] = round(found["ra"], 5), round(found["dec"], 5)
    found["constellation"] = str(get_constellation(SkyCoord(found["ra"], found["dec"], unit="deg")))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(found))
    return found
