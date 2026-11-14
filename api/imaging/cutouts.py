"""Find SPHEREx frames covering a position and fetch small cutouts of them, cached on disk.

Person C imports `get_cutouts` for spectra; keep the `Cutout` fields stable.
"""

import hashlib
import io
import json
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import astropy.units as u
import httpx
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from astroquery.ipac.irsa import Irsa

from api.imaging.config import BAD_FLAG_NAMES, CACHE_DIR, COLLECTIONS, MAX_WORKERS

log = logging.getLogger(__name__)
logging.getLogger("astropy").setLevel(logging.WARNING)  # SIP "-SIP suffix" notice on every frame


@dataclass
class Cutout:
    img: np.ndarray  # MJy/sr, zodi subtracted, bad pixels NaN
    var: np.ndarray  # (MJy/sr)^2
    wave: np.ndarray  # per-pixel central wavelength, um
    wcs: WCS  # celestial WCS of this cutout
    mjd: float
    detector: int
    url: str


def query_frames(ra: float, dec: float) -> list[tuple[str, float, int]]:
    """(access_url, mjd, detector) for every frame containing the position.

    Cached for a day (QR3 updates weekly); a stale cache is used if IRSA is down.
    """
    path = CACHE_DIR / "queries" / f"{ra:.4f}_{dec:+.4f}_{'_'.join(COLLECTIONS)}.json"
    if path.exists() and time.time() - path.stat().st_mtime < 86400:
        return [tuple(f) for f in json.loads(path.read_text())]
    for i in range(4):
        try:
            pos = (SkyCoord(ra, dec, unit="deg"), 1 * u.arcsec)
            t = Irsa.query_sia(pos=pos, collection=COLLECTIONS)
            break
        except Exception as e:  # pyvo raises DALServiceError on IRSA's 503 "busy"
            log.info("SIA query failed (%s), retrying", e)
            time.sleep(3 * (i + 1))
    else:
        if path.exists():
            log.warning("IRSA unavailable, using stale frame list")
            return [tuple(f) for f in json.loads(path.read_text())]
        raise RuntimeError("IRSA SIA unavailable")
    frames = [
        (str(r["access_url"]), float(r["t_min"]), int(str(r["energy_bandpassname"])[-1])) for r in t
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(frames))
    return frames


def get_cutouts(ra: float, dec: float, fov: float) -> list[Cutout]:
    return fetch_cutouts(ra, dec, fov)[0]


def fetch_cutouts(ra: float, dec: float, fov: float) -> tuple[list[Cutout], int]:
    """Cutouts plus the number of frames that failed to download."""
    ra, dec, fov = round(ra, 4), round(dec, 4), round(fov, 3)  # stable cache keys
    frames = query_frames(ra, dec)
    size = round(fov * 1.5, 4)  # margin so rotated frames still fill the output square
    with httpx.Client(timeout=120) as client, ThreadPoolExecutor(MAX_WORKERS) as pool:
        results = list(pool.map(lambda f: _fetch(client, *f, ra, dec, size), frames))
    cuts = [c for c in results if c is not None]
    return cuts, len(results) - len(cuts)


def _fetch(
    client: httpx.Client, url: str, mjd: float, det: int, ra: float, dec: float, size: float
) -> Cutout | None:
    cut_url = f"{url}?center={ra},{dec}&size={size}"
    path = CACHE_DIR / "cutouts" / f"{hashlib.sha1(cut_url.encode()).hexdigest()}.npz"
    if not path.exists():
        data = _download(client, cut_url)
        if data is None:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp.npz")
        np.savez_compressed(tmp, **_slim(data), mjd=mjd, detector=det)
        tmp.replace(path)  # atomic: a crash never leaves a half-written cache file
    z = np.load(path)
    return Cutout(
        img=z["img"],
        var=z["var"],
        wave=z["wave"],
        wcs=WCS(fits.Header.fromstring(str(z["hdr"]))),
        mjd=float(z["mjd"]),
        detector=int(z["detector"]),
        url=url,
    )


def _download(client: httpx.Client, url: str, tries: int = 6) -> bytes | None:
    for i in range(tries):
        try:
            r = client.get(url)
            if r.status_code == 200:
                return r.content
            log.info("HTTP %s for %s", r.status_code, url)
        except httpx.HTTPError as e:
            log.info("%s for %s", e, url)
        time.sleep(2 * (i + 1) + random.random())  # IRSA asks for "retry later" on 503
    log.warning("giving up on %s", url)
    return None


def _slim(data: bytes) -> dict[str, np.ndarray]:
    """Keep only what we use. The EPSF table is ~4 MB of every ~4.2 MB cutout."""
    with fits.open(io.BytesIO(data)) as h:
        hdr = h["IMAGE"].header
        img = (h["IMAGE"].data - h["ZODI"].data).astype(np.float32)
        img[(h["FLAGS"].data & _bad_mask(h["FLAGS"].header)) != 0] = np.nan
        w = WCS(hdr, fobj=h, key="W")
        w.sip = None
        yy, xx = np.mgrid[: img.shape[0], : img.shape[1]]
        wave = w.pixel_to_world(xx, yy)[0].to_value(u.um).astype(np.float32)
        celestial = WCS(hdr).to_header(relax=True)  # keeps SIP distortion
        return {
            "img": img,
            "var": h["VARIANCE"].data.astype(np.float32),
            "wave": wave,
            "hdr": np.array(celestial.tostring()),
        }


def _bad_mask(flags_header: fits.Header) -> int:
    bits = {flags_header[k]: int(k[4:]) for k in flags_header["MSKN*"]}
    return sum(1 << bits[n] for n in BAD_FLAG_NAMES if n in bits)
