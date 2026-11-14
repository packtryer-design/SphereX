# Backend Imaging: Handoff

Read this first if you're picking up Person A's work. The full design is in [BACKEND_IMAGING.md](BACKEND_IMAGING.md) and the team plan is in [PLAN.md](PLAN.md).

**Status at 14 Nov, ~12:40:** the pipeline works end to end on live SPHEREx data and passes the science check. What's left is running it on more targets, deploying it, and making the demo resilient (§4).

---

## 1. Get running (5 minutes)

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv numpy astropy astroquery reproject pillow fastapi uvicorn httpx pytest pytest-cov ruff
```

`pip install -e ".[dev]"` **hung on Windows** during setup. Installing the packages by name, as above, works. CI installs the project normally.

```bash
.venv/Scripts/uvicorn api.main:app --reload            # API on http://127.0.0.1:8000
PYTHONPATH=src .venv/Scripts/python -m pytest -q        # 6 tests, all passing
.venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .
```

Try it: http://127.0.0.1:8000/api/frames?ra=269.4462&dec=4.7682&mode=rgb

---

## 2. What exists

| File | What it does |
|---|---|
| [api/imaging/config.py](../api/imaging/config.py) | Every setting: data collections, cache folder, pixel scale, number of parallel downloads, epoch gap, which flags to mask |
| [api/imaging/cutouts.py](../api/imaging/cutouts.py) | Searches IRSA for frames (cached 24 h, falls back to the last saved list if IRSA is down), downloads cutouts with retries, keeps each one as a ~73 KB `.npz` instead of 4.2 MB. **`get_cutouts()` is Person C's entry point for spectra.** |
| [api/imaging/pipeline.py](../api/imaging/pipeline.py) | Aligns every frame to one grid → converts to σ (noise) units → splits into epochs → stacks → stretches → writes PNGs. Modes: `single`, `epoch`, `rgb`, `diff`. Each response is cached as JSON, but only if every frame downloaded. |
| [api/main.py](../api/main.py) | `GET /api/frames` with input checks (bad input → 422; IRSA down and nothing cached → 503). PNGs are served from `/cache/...`. |
| [scripts/warm_cache.py](../scripts/warm_cache.py) | Builds all 4 modes for one position, or for every target in `data/targets.json` |
| [scripts/check_motion.py](../scripts/check_motion.py) | Science check: Barnard's Star's measured shift against its known proper motion, plus a field star that should stay still |
| [tests/test_imaging.py](../tests/test_imaging.py) | Offline tests: epoch splitting, long-epoch chunking, alignment of a rotated frame, RGB |

---

## 3. What's verified

Barnard's Star (RA 269.4462, Dec 4.7682, field of view 0.1°):

- 358 frames over 3 epochs, spanning about 1 year.
- `check_motion.py`: Barnard's Star moved **1.52 px**, against **1.66 px** expected. A field star moved **0.02 px**, so the alignment is correct.
- RGB shows a red → blue trail toward the north. The difference frames show a white/black pair. Field stars come out white or cancel out.
- Timing: the first download takes several minutes. Building a mode from already-downloaded cutouts takes about 45 s, and a cached response is instant.

**API contract additions** (B and C need to know these): each frame also carries `n_frames`. In stacked modes, `detector` and `wavelength_um` are `null` when detectors are combined, and `epoch` is `null` in `rgb`.

---

## 4. Next steps, in order

| # | Task | How | Done when |
|---|---|---|---|
| 1 | **Tell C that `get_cutouts()` is ready** | Point them to §2. Every `Cutout` has `img`, `var` (variance), `wave` (µm per pixel), `wcs`, `mjd` and `detector`. | C is building `/api/spectrum` on top of it |
| 2 | **Warm the cache for every target** | Get `data/targets.json` from C, then run `python scripts/warm_cache.py` in the background. Until that file exists, run `python scripts/warm_cache.py RA DEC`. | Every target × 4 modes is cached |
| 3 | **Check WISE 0855** (RA 133.7951, Dec −7.2451; the challenge coordinates are an older epoch, so get current ones from C) | Look at `mode=epoch&detector=5` and `detector=6`. It is nearly invisible at short wavelengths. | It's visible in at least one view. If not, tell C, because the pitch depends on it. |
| 4 | **Check R Draconis** (close to the ecliptic pole) | Look at the epoch count in `mode=epoch`. If it comes back as 1 long epoch, the 60-day chunking rule in `split_epochs` should split it. | It has more than one epoch |
| 5 | **Deploy the API** next to B's frontend | `uvicorn api.main:app --host 0.0.0.0 --port $PORT` on Render, Fly or Cloud Run. Set `BLINK_CACHE` to a writable folder. | A public URL returns the Barnard's Star RGB |
| 6 | **Demo snapshot** | Copy `cache/png/` and `cache/responses/` for the demo targets into `cache/demo/` (git keeps that folder) and commit it. B can serve it as static files if IRSA or the server goes down. | The demo works with Wi-Fi off |
| 7 | **Feature freeze at 08:00 on 15 Nov.** Bug fixes only after that. | | |

---

## 5. Known issues and gotchas

- **IRSA often answers 503 "Server busy".** The retries handle it, but a cold target can take minutes. Never run the demo on a target that hasn't been warmed.
- **Use current coordinates, not J2000.** Barnard's Star has moved about 4.5′ since 2000, which nearly takes it out of the field. `SkyCoord.from_name` returns J2000.
- **Cache keys round RA/Dec to 4 decimals.** A different 5th decimal still hits the same cache, but a different field of view or mode builds a new response.
- **Clear the response cache after changing the pipeline:** `rm -rf cache/responses cache/png`. Downloaded cutouts in `cache/cutouts/` can stay.
- **Paired light/dark spots around bright stars in `diff`** come from the PSF changing orientation between epochs. That's expected, not a bug. Mention it in the explainer.
- **mypy hasn't been run locally.** `pyproject.toml` excludes `api.*` from strict checking, so CI should pass. Check the first CI run.
- **Ideas left unbuilt (only if there's time):**
  - S3 range reads as a faster download path when hosted in the US (bucket `nasa-irsa-spherex`)
  - Re-run `check_motion.py` with Epsilon Indi B's proper motion
