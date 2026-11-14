# Demo snapshot

Finished results (API responses, PNGs, spectra, frame lists, catalog lookups) for the demo
objects. The server copies this folder into its cache at startup (`seed_cache` in
`api/imaging/pipeline.py`), so a fresh deploy opens these objects instantly and keeps working
if IRSA is slow or down. Existing cache files are never overwritten.

Refresh it after warming the cache:

    python scripts/warm_cache.py barnards-star eps-indi-b wise-0855 rw-aur r-dra orion
    python scripts/demo_snapshot.py

Raw cutouts are never copied here (~70 KB each, hundreds per object).
