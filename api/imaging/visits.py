"""When SPHEREx looked at a position: real visit dates, without downloading any images.

Uses the same frame search and epoch split as the image pipeline, so the dates match
what `/api/frames?mode=epoch` later builds. Fast (one cached IRSA query), so the
front end can show the timeline, or say "no data here", before images are ready.
"""

from typing import Any

import numpy as np

from api.imaging.cutouts import query_frames
from api.imaging.pipeline import split_epochs

ALL_DETECTORS = [1, 2, 3, 4, 5, 6]


def list_visits(ra: float, dec: float) -> dict[str, Any]:
    ra, dec = round(ra, 4), round(dec, 4)
    frames = query_frames(ra, dec)
    if not frames:
        return {"target": {"ra": ra, "dec": dec}, "n_frames": 0, "visits": []}
    mjd = np.array([f[1] for f in frames])
    det = np.array([f[2] for f in frames])
    epochs = split_epochs(mjd)
    visits = []
    for e in sorted(set(epochs.tolist())):
        m = epochs == e
        dets = sorted({int(d) for d in det[m]})
        visits.append(
            {
                "epoch": int(e),
                "mjd_start": round(float(mjd[m].min()), 4),
                "mjd_end": round(float(mjd[m].max()), 4),
                "n_frames": int(m.sum()),
                "detectors": dets,
                "full_coverage": dets == ALL_DETECTORS,
            }
        )
    return {"target": {"ra": ra, "dec": dec}, "n_frames": len(frames), "visits": visits}
