"""Known asteroids and comets in a field, from IMCCE SkyBoT, at each frame time.

A moving dot that matches a SkyBoT entry is a known body. One with no match is a
"candidate for review" (cross-check with JPL SBIdent before saying anything more).
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
import numpy as np
from astropy.coordinates import Angle

from api.imaging.config import CACHE_DIR
from api.imaging.cutouts import query_frames
from api.imaging.pipeline import split_epochs

SKYBOT_URL = "https://ssp.imcce.fr/webservices/skybot/api/conesearch.php"
VMAG_LIMIT = 20.0  # fainter than this SPHEREx won't see it
TIME_STEP_D = 0.25  # frames closer than this share one SkyBoT query
MAX_QUERIES = 40
MJD_TO_JD = 2400000.5


def skybot(mjd: float, ra: float, dec: float, radius_deg: float) -> list[dict]:
    p = CACHE_DIR / "skybot" / f"{mjd:.3f}_{ra:.4f}_{dec:+.4f}_{radius_deg:.3f}.json"
    if p.exists():
        return list(json.loads(p.read_text()))
    r = httpx.get(
        SKYBOT_URL,
        params={
            "-ep": mjd + MJD_TO_JD,
            "-ra": ra,
            "-dec": dec,
            "-rd": radius_deg,
            "-mime": "json",
            "-output": "basic",
            "-loc": "500",
            "-from": "SpotX",
        },
        timeout=60,
    )
    r.raise_for_status()
    try:
        rows = r.json()
    except ValueError:  # SkyBoT answers plain text when the field is empty
        rows = []
    out = []
    for row in rows if isinstance(rows, list) else []:
        vmag = row.get("VMag (mag)")
        if vmag is not None and vmag > VMAG_LIMIT:
            continue
        out.append(
            {
                "name": row["Name"],
                "number": row.get("Num"),
                "class": row.get("Class"),
                "vmag": vmag,
                "ra": round(float(Angle(row["RA (hms)"], unit="hourangle").deg), 6),
                "dec": round(float(Angle(row["DEC (dms)"], unit="deg").deg), 6),
                "rate_arcsec_h": round(
                    float(np.hypot(row["dRA (arcsec/h)"], row["dDEC (arcsec/h)"])), 2
                ),
            }
        )
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out))
    return out


def build_asteroids(ra: float, dec: float, fov: float) -> dict[str, Any]:
    ra, dec, fov = round(ra, 4), round(dec, 4), round(fov, 3)
    frames = query_frames(ra, dec)
    target = {"ra": ra, "dec": dec, "fov": fov}
    if not frames:
        return {"target": target, "source": "IMCCE SkyBoT", "times": [], "objects": []}
    mjd = np.array(sorted(f[1] for f in frames))
    ep = split_epochs(mjd)
    # one query per TIME_STEP_D slot; keep the busiest slots if there are too many
    slots: dict[float, int] = {}
    for m, e in zip(mjd, ep, strict=True):
        slots.setdefault(round(m / TIME_STEP_D) * TIME_STEP_D, int(e))
    times = sorted(slots)
    if len(times) > MAX_QUERIES:
        times = [times[i] for i in np.linspace(0, len(times) - 1, MAX_QUERIES).astype(int)]
    radius = fov * 0.75
    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(lambda t: skybot(t, ra, dec, radius), times))

    half = fov / 2
    objects: dict[str, dict] = {}
    for t, rows in zip(times, results, strict=True):
        for o in rows:
            dx = (o["ra"] - ra) * np.cos(np.radians(dec))
            if abs(dx) > half or abs(o["dec"] - dec) > half:
                continue
            obj = objects.setdefault(
                o["name"],
                {k: o[k] for k in ("name", "number", "class", "vmag")} | {"positions": []},
            )
            obj["positions"].append(
                {
                    "mjd": round(t, 3),
                    "epoch": slots[t],
                    "ra": o["ra"],
                    "dec": o["dec"],
                    "rate_arcsec_h": o["rate_arcsec_h"],
                }
            )
    objs = sorted(objects.values(), key=lambda o: o["vmag"] if o["vmag"] is not None else 99)
    return {
        "target": target,
        "source": (
            "IMCCE SkyBoT (geocentric; SPHEREx is in low Earth orbit, "
            "so near-Earth objects can be off by a few arcsec)"
        ),
        "times": [{"mjd": round(t, 3), "epoch": slots[t]} for t in times],
        "objects": objs,
    }
