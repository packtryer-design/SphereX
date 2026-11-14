"""Star catalogues for ghosts and blend checks: Gaia DR3 (optical) and CatWISE2020 (infrared).

Gaia: ESA archive first; its anonymous queue is shared by everyone and answers "queue full"
on busy days, so the IRSA copy of the same table is the fallback.
CatWISE2020 (Marocco et al. 2021, ApJS 253, 8) measured motions in the infrared, so it has the
cold brown dwarfs Gaia can't see (WISE 0855 is invisible to Gaia).
Fallback idea from ParallaX (github.com/abed-r-j/parallax-spherex); code is ours.
"""

from __future__ import annotations

import csv
import io
import json
import warnings
from collections.abc import Callable

import httpx
import numpy as np

from api.imaging.config import CACHE_DIR

IRSA_TAP = "https://irsa.ipac.caltech.edu/TAP/sync"
MAX_STARS = 300
G_LIMIT = 17.0  # fainter than this SPHEREx won't see it at 6" pixels
W2_LIMIT = 16.0  # CatWISE: brown dwarfs are bright in W2 (4.6 um), faint in W1
CATWISE_EPOCH_MJD = 57170.0  # ra_pm/dec_pm reference epoch (2015.4)
MIN_W2_SNR = 5.0
PM_SIGMA = 5.0  # CatWISE motion counts only above this significance


def _cone(table: str, ra: float, dec: float, radius: float) -> str:
    return (
        f"FROM {table} WHERE CONTAINS(POINT('ICRS', ra, dec), "
        f"CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, {radius:.5f})) = 1"
    )


def _num(v: object) -> float | None:
    try:
        x = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return x if np.isfinite(x) else None


def _irsa_csv(query: str) -> list[dict[str, str]]:
    r = httpx.get(IRSA_TAP, params={"QUERY": query, "FORMAT": "CSV"}, timeout=60)
    r.raise_for_status()
    if "<VOTABLE" in r.text[:500]:  # IRSA reports query errors as VOTable
        raise RuntimeError(r.text[:300])
    return list(csv.DictReader(io.StringIO(r.text)))


def _gaia_row(get: Callable[[str], object]) -> dict:
    return {
        "source_id": str(get("source_id")),
        "ra": _num(get("ra")),
        "dec": _num(get("dec")),
        "pmra": _num(get("pmra")),
        "pmdec": _num(get("pmdec")),
        "parallax": _num(get("parallax")),
        "g_mag": round(_num(get("phot_g_mean_mag")) or 99.0, 2),
    }


def _gaia_query(table: str, ra: float, dec: float, radius: float) -> str:
    return (
        f"SELECT TOP {MAX_STARS} source_id, ra, dec, pmra, pmdec, parallax, phot_g_mean_mag "
        f"{_cone(table, ra, dec, radius)} AND phot_g_mean_mag < {G_LIMIT} "
        "ORDER BY phot_g_mean_mag"
    )


def _gaia_esa(ra: float, dec: float, radius: float) -> list[dict]:
    from astroquery.gaia import Gaia

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tab = Gaia.launch_job(_gaia_query("gaiadr3.gaia_source", ra, dec, radius)).get_results()
    names = {c.lower(): c for c in tab.colnames}
    rows = []
    for r in tab:

        def get(k: str, r=r) -> object:
            v = r[names[k]]
            return None if np.ma.is_masked(v) else v

        rows.append(_gaia_row(get))
    return rows


def _gaia_irsa(ra: float, dec: float, radius: float) -> list[dict]:
    return [_gaia_row(r.get) for r in _irsa_csv(_gaia_query("gaia_dr3_source", ra, dec, radius))]


def gaia_cone(ra: float, dec: float, radius: float) -> list[dict]:
    """Gaia DR3 stars (G < 17) at epoch 2016.0. ESA first, IRSA copy if ESA is busy."""
    try:
        return _gaia_esa(ra, dec, radius)
    except Exception:
        return _gaia_irsa(ra, dec, radius)


def catwise_cone(ra: float, dec: float, radius: float) -> list[dict]:
    """CatWISE2020 sources (W2 < 16) at epoch 2015.4, proper motions in mas/yr."""
    q = (
        f"SELECT TOP {MAX_STARS} source_name, ra_pm, dec_pm, pmra, pmdec, sigpmra, sigpmdec, "
        f"w1mpro, w2mpro, w2snr, ab_flags "
        f"{_cone('catwise_2020', ra, dec, radius)} AND w2mpro < {W2_LIMIT} ORDER BY w2mpro"
    )
    out = []
    for r in _irsa_csv(q):
        flags = (r.get("ab_flags") or "").strip()
        if (_num(r.get("w2snr")) or 0) < MIN_W2_SNR or (len(flags) == 2 and flags[1] != "0"):
            continue  # faint, or W2 flagged as artifact (halo, ghost, diffraction spike)
        pmra, pmdec = _num(r.get("pmra")), _num(r.get("pmdec"))
        spm = np.hypot(_num(r.get("sigpmra")) or np.inf, _num(r.get("sigpmdec")) or np.inf)
        if pmra is not None and pmdec is not None and np.hypot(pmra, pmdec) < PM_SIGMA * spm:
            pmra = pmdec = 0.0  # motion not significant: treat as fixed
        out.append(
            {
                "source_id": "CWISE " + r["source_name"].strip(),
                "ra": _num(r["ra_pm"]),
                "dec": _num(r["dec_pm"]),
                "pmra": None if pmra is None else pmra * 1000,  # catalogue is arcsec/yr
                "pmdec": None if pmdec is None else pmdec * 1000,
                "parallax": None,
                "w1_mag": _num(r.get("w1mpro")),
                "w2_mag": _num(r.get("w2mpro")),
            }
        )
    return out


def allwise_cone(ra: float, dec: float, radius: float) -> list[dict]:
    """AllWISE W2 photometry (epoch ~2010.5), for the spectrum's flux sanity check.
    AllWISE rather than CatWISE: CatWISE splits fast movers like WISE 0855 into pieces."""
    q = (
        "SELECT designation, ra, dec, w2mpro, w2sigmpro, w2sat "
        f"{_cone('allwise_p3as_psd', ra, dec, radius)}"
    )
    return [
        {
            "source_id": "AllWISE " + r["designation"].strip(),
            "ra": _num(r["ra"]),
            "dec": _num(r["dec"]),
            "w2_mag": _num(r.get("w2mpro")),
            "w2_err": _num(r.get("w2sigmpro")),
            "w2_sat": _num(r.get("w2sat")) or 0.0,  # fraction of saturated pixels
        }
        for r in _irsa_csv(q)
    ]


def _cached(kind: str, fn: Callable, ra: float, dec: float, radius: float) -> list[dict]:
    p = CACHE_DIR / kind / f"{ra:.4f}_{dec:+.4f}_{radius:.3f}.json"
    if p.exists():
        return list(json.loads(p.read_text()))
    rows = fn(ra, dec, radius)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows))
    return rows


def gaia_cached(ra: float, dec: float, radius: float) -> list[dict]:
    return _cached("gaia", gaia_cone, ra, dec, radius)


def catwise_cached(ra: float, dec: float, radius: float) -> list[dict]:
    return _cached("catwise", catwise_cone, ra, dec, radius)


def allwise_cached(ra: float, dec: float, radius: float) -> list[dict]:
    return _cached("allwise", allwise_cone, ra, dec, radius)
