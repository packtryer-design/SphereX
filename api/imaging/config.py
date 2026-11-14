import os
from pathlib import Path

# New data releases: add the collection name here, nothing else changes.
COLLECTIONS = ["spherex_dr1", "spherex_qr3"]

CACHE_DIR = Path(os.environ.get("BLINK_CACHE", "cache"))
PIXEL_SCALE_ARCSEC = 6.15  # s_pixel_scale reported by IRSA for every frame
MAX_WORKERS = 6  # IRSA answers 503 "Server busy" readily; keep this modest
EPOCH_GAP_DAYS = 30  # recon: in-epoch gaps reach 25 d, between-epoch gaps exceed 100 d
MAX_EPOCH_DAYS = 60  # near the ecliptic poles there may be no gap; chunk long epochs
MAX_DLAMBDA = 0.025  # diff pairs must match in wavelength to ~1 spectral channel (R ~ 40)

# Only clearly broken pixels. Not SOURCE (marks real stars), not OVERFLOW/NONLINEAR
# (they would punch holes in bright stars like Barnard's Star).
BAD_FLAG_NAMES = ["SUR_ERROR", "NONFUNC", "MISSING_DATA", "HOT", "COLD"]
