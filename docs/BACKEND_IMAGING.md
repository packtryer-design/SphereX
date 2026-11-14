# Backend Imaging Plan (Person A)

Your job: take coordinates and return a stack of **aligned PNG frames** that make motion easy to see. You also write the cutout fetcher that Person C's spectrum code builds on.

Read with [PLAN.md](PLAN.md). Any change to the API contract has to be agreed with B and C first.

---

## 1. What you own

| Piece | Used by |
|---|---|
| `get_cutouts(ra, dec, fov)`: IRSA search, cutout download, cache | **C (spectrum), due 13:00** |
| `GET /api/frames`: modes `single`, `epoch`, `rgb`, `diff` | B (viewer) |
| Frame alignment, per-frame normalization, stacking, the stretch | internal |
| Bad-pixel masking (FLAGS) | internal |
| Cache warming, the static demo snapshot, backend deploy | everyone |

**Not yours:** spectra, Gaia ghosts, asteroid labels (all C), and anything in the browser (B).

---

## 2. Files

```
api/
  main.py              # FastAPI app, shared with C. You add /api/frames + /cache static mount
  imaging/
    config.py          # COLLECTIONS, CACHE_DIR, PIXEL_SCALE, BAD_FLAG_NAMES, MAX_WORKERS
    cutouts.py         # query_frames(), get_cutouts()        <- C imports this
    pipeline.py        # align, normalize, split_epochs, stack, rgb, diff, to_png
scripts/warm_cache.py  # pre-fills cache for the demo targets
tests/test_imaging.py  # offline tests on synthetic data
cache/                 # gitignored, except cache/demo/ (see §6)
```

### Setup (first 15 minutes, or CI goes red on your first push)

The template's CI runs `ruff`, then `mypy --strict` on `src/` and `tests/`, then `pytest` on Python 3.10–3.13 and on Windows and macOS. Make three changes to `pyproject.toml`:

```toml
dependencies = ["numpy", "astropy", "astroquery", "reproject", "pillow",
                "fastapi", "uvicorn", "httpx"]

[tool.pytest.ini_options]
pythonpath = ["."]          # so tests can `import api`

[[tool.mypy.overrides]]     # hackathon speed: don't strict-check api/ or untyped astro libs
module = ["api.*", "astroquery.*", "reproject.*"]
ignore_errors = true
ignore_missing_imports = true
```

If `reproject` has no wheel for one of the matrix Pythons and CI fails on install, ask the team before you trim the matrix.

---

## 3. Recon, 11:00–12:00 (answer these before writing pipeline code)

> **Done 14 Nov. Answers measured on Barnard's Star (RA 269.4462, Dec 4.7682):**
> - 358 frames (239 from DR1 + 119 from QR3), about 60 per detector.
> - Time: `t_min` is MJD, running 60902 → 61305 (Aug 2025 → Sep 2026). The header also has `MJD-AVG`.
> - **3 epochs.** The gaps between epochs are over 100 days. Each epoch spans 37–55 days, with gaps of up to 25 days inside it.
> - Pixel scale: 6.15″, from `s_pixel_scale`.
> - Detector: from the `energy_bandpassname` column (`SPHEREx-D3`), so the filename regex isn't needed.
> - **Cutout size: 4.15 MB, of which about 3.9 MB is the EPSF table.** One download took 16.6 s, and **IRSA answered 503 "Server busy, retry later" 4 times first.** So retrying with backoff is required.
> - S3 (`nasa-irsa-spherex`, public, us-east-1) supports range reads at about 1.9 MB/s, but each request takes about 1.3 s to start from the UAE. Plan B only.
> - Wavelength: `WCS(..., key="W").pixel_to_world` returns `[SpectralCoord, Quantity]`, both in µm.
> - Flags: the bits are named in the header. Mask only SUR_ERROR, NONFUNC, MISSING_DATA, HOT and COLD. **Don't mask SOURCE**, which marks real stars. Don't mask OVERFLOW or NONLINEAR either, because they would punch holes in bright stars.

Run this in a notebook and post the answers in the team chat:

```python
from astroquery.ipac.irsa import Irsa
from astropy.coordinates import SkyCoord
import astropy.units as u

c = SkyCoord(ra, dec, unit="deg")  # from C's targets.json, NOT SkyCoord.from_name (see §8)
t = Irsa.query_sia(pos=(c, 1 * u.arcsec), collection=["spherex_dr1", "spherex_qr3"])
print(len(t), t.colnames)
```

| Question | Where to look | Why it matters |
|---|---|---|
| Frames per target | `len(t)` | Request time and cache size |
| Which column holds the time? Is it MJD? | probably `t_min`, the ObsCore standard. If not, look in the IMAGE header | Epoch split |
| How many epochs, and how many days apart? | sort the times and look at the gaps | Is there motion to show at all? |
| Pixel scale | `WCS(hdr).proj_plane_pixel_scales()` | Output grid (expected about 6.2″) |
| Size and time of one cutout download | download one with `size=0.15` | **The ePSF extension is copied whole into every cutout, so expect ~2 MB each no matter how small the cutout.** Measure it. |
| Flag names | the `MSKN*` / `MSKD*` keys in the FLAGS header | Fills `BAD_FLAG_NAMES` |
| Detector number | regex `D(\d)_spx` on the filename in `access_url` | Labels and stacking |

**If you have to use the organizers' event data** (local full frames, not the IRSA service): raise it at the 11:00 sync. `get_cutouts` would then need a local source that slices files with `astropy.nddata.Cutout2D`, plus a footprint index built once at startup. Budget 2 extra hours for that.

---

## 4. Pipeline

```
search (SIA) → download cutouts in parallel → slim each to .npz → mask bad pixels, subtract zodi
→ reproject onto one grid → normalize to σ units → [split epochs → stack] → stretch → PNG
```

### 4.1 `get_cutouts`: download once, keep it small (due 13:00)

- Cutout URL: `f"{access_url}?center={ra:.5f},{dec:.5f}&size={fov * 1.5:.4f}"`. Ask for 1.5× the field of view. Frames are taken at different rotations, so the extra margin keeps the output square filled after reprojection.
- Round `ra` and `dec` to 4 decimals (0.36″) and `fov` to 3 before building the URL. Otherwise repeat requests never hit the cache.
- Download with a thread pool (`MAX_WORKERS = 8`). That's polite to IRSA and fast enough.
- **Don't cache the raw FITS file.** Open it, keep only what's needed, and save an `.npz` (about 70 KB instead of about 2 MB):

```python
with fits.open(io.BytesIO(resp.content)) as hdul:
    hdr = hdul["IMAGE"].header
    img = hdul["IMAGE"].data - hdul["ZODI"].data  # remove the zodiacal glow
    var = hdul["VARIANCE"].data
    bad = (hdul["FLAGS"].data & BAD_MASK) != 0
    img[bad] = np.nan
    w = WCS(hdr, fobj=hdul, key="W")
    w.sip = None  # per-pixel wavelength map
    yy, xx = np.mgrid[: img.shape[0], : img.shape[1]]
    wave, _ = w.pixel_to_world(xx, yy)  # check the type in recon; expect a Quantity
np.savez(
    path,
    img=img,
    var=var,
    wave=u.Quantity(wave).to_value(u.um),
    hdr=hdr.tostring(),
    mjd=t_min,
    detector=det,
)
```

- `BAD_MASK` is built from flag *names*, not hard-coded bit numbers. Start with an empty `BAD_FLAG_NAMES` and fill it after recon:

```python
bits = {fh[k]: int(k[4:]) for k in fh["MSKN*"]}  # name -> bit
BAD_MASK = sum(1 << bits[n] for n in BAD_FLAG_NAMES if n in bits)
```

- Return a list of `Cutout` records with `img`, `var`, `wave`, `wcs`, `mjd`, `detector` and `url`. **C uses `var` and `wave`, so freeze this shape at 13:00.**
- Retries: up to 6 tries with linear backoff on 503 and timeouts. If all 6 fail, the frame is logged and skipped.

### 4.2 Align everything to one grid

```python
def target_grid(ra, dec, fov, scale=6.2):
    n = int(np.ceil(fov * 3600 / scale)) | 1  # odd size: target lands on the centre pixel
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [(n + 1) / 2] * 2
    w.wcs.cdelt = [-scale / 3600, scale / 3600]  # north up, east left
    return w, (n, n)


aligned, footprint = reproject_interp((c.img, c.wcs), out_wcs, shape_out=shape)
```

- Bad pixels carry through as NaN. Drop a frame if more than 50% of its pixels are NaN (the target sat at the detector edge). Report the share of NaN pixels as `flagged_frac`.
- **Get this right before anything else.** Every later step assumes stars stay put.

### 4.3 Normalize to σ units

Each frame is at a different wavelength and has a different noise level, so convert to "how many σ above the background":

```python
_, med, std = sigma_clipped_stats(aligned, sigma=3)
z = (aligned - med) / std
```

After that one change, frames from different detectors can share one stretch and be stacked directly.

### 4.4 Epochs

```python
order = np.argsort(mjd)
epoch = np.empty(len(mjd), int)
epoch[order] = 1 + np.concatenate(
    [[0], np.cumsum(np.diff(mjd[order]) > 30)]
)  # new epoch after a 30-day gap
```

- **Edge case:** near the ecliptic poles SPHEREx observes almost continuously, so there may be no 30-day gap at all. R Draconis sits about 9° from the north ecliptic pole. If an epoch spans more than 60 days, cut it into chunks of about 30 days.

### 4.5 Stacks (`mode=epoch`)

- Group by `(epoch, detector)` and take `np.nanmedian` (about 17 frames per group, about 4× better signal-to-noise). The median also drops cosmic rays, and drops fast asteroids too, which is fine for this view.
- `detector=all`: take `np.nanmean` of the 6 per-detector stacks. **Use the mean, not the median.** A brown dwarf that only shows up in detectors 5–6 would vanish in a median.

### 4.6 Stretch and PNG

```python
vmin, vmax = -2.0, np.nanpercentile(all_z_in_this_response, 99.5)  # ONE stretch per response
x = np.clip((z - vmin) / (vmax - vmin), 0, 1)
x = np.nan_to_num(AsinhStretch(0.1)(x), nan=0)
Image.fromarray((x * 255).astype(np.uint8)[::-1]).save(png)  # [::-1]: FITS rows go bottom-up
```

A separate stretch per frame makes the flipbook flicker, and it's the usual reason images look all black.

### 4.7 RGB, motion in one picture (`mode=rgb`)

- With 3 or more epochs: R = first, G = middle, B = last (each a stretched all-detector stack). `np.dstack([r, g, b])`.
- With 2 epochs: R = epoch 1, G = B = epoch 2. A star that stays still comes out white; a moving one shows red at its old position and cyan at its new one.

### 4.8 Difference (`mode=diff`)

- Subtract **per detector, then average**: `mean_d(stack[e, d] - stack[1, d])`. Subtracting all-detector stacks would mix in wavelength differences.
- Display mid-gray as zero, with fixed limits of ±5σ: `x = clip(diff / 10 + 0.5, 0, 1)`.
- Expect leftover residue around bright stars, because the PSF orientation changes between epochs. Mention it in the explainer.

---

## 5. API

`GET /api/frames?ra=&dec=&fov=0.1&mode=single|epoch|rgb|diff&detector=all|1..6`

- **Check the inputs, because this is a public endpoint:** `0 ≤ ra < 360`, `-90 ≤ dec ≤ 90`, `fov` limited to 0.02–0.5°, and mode and detector checked against fixed lists. Anything else returns HTTP 422 (FastAPI `Query(ge=, le=)` handles this).
- Sort frames by `mjd`. B's time ↔ color switch re-sorts them by `wavelength_um`.
- The `wavelength_um` reported for each frame is the value of `wave` at the target pixel.
- Save each full response to `cache/responses/<key>.json`, where the key is built from the rounded inputs, and return the saved file when it already exists.
- Serve the PNGs with `app.mount("/cache", StaticFiles(directory="cache"))`.

**Contract additions to propose at 11:00** (needed for the stacked modes):

```jsonc
{"png": "...", "mjd": 60812.4, "epoch": 1,
 "detector": null,          // null = all-detector stack
 "wavelength_um": null,     // null when the frame mixes detectors
 "n_frames": 17,            // frames combined into this PNG (1 in single mode)
 "flagged_frac": 0.02}
```

---

## 6. Keeping the demo alive

- **A cold target is slow.** About 300 cutouts × about 2 MB at 8 in parallel takes minutes, and hosting platforms often cut requests off at 60–300 s. The demo has to come from a warm cache.
- `scripts/warm_cache.py`: for every entry in `targets.json` plus 3I/ATLAS, call the pipeline in all 4 modes. Start it before you sleep.
- **Static snapshot:** copy the PNGs and response JSONs for the demo targets into `cache/demo/` and commit them (expect around 10 MB). B can serve them as static files if the backend or IRSA goes down during judging.
- **Deploy** the API next to B's frontend by the 15:00 sync, even if all it does is return fixture data. Use Render, Fly or Cloud Run with `uvicorn api.main:app --host 0.0.0.0 --port $PORT`. Their disks are usually wiped on restart, which is one more reason for the committed snapshot.

---

## 7. Proving it works

**Unit tests** (`tests/test_imaging.py`, offline, synthetic data, so they pass in CI):

1. `split_epochs` on MJDs `[0, 1, 2, 183, 184, 366]` → `[1, 1, 1, 2, 2, 3]`.
2. A fake star at a known RA/Dec in a randomly rotated TAN frame → after `target_grid` and `reproject_interp`, its peak is within 0.5 px of the center.
3. `make_rgb` on 3 identical inputs → R == G == B everywhere (a still star comes out white).

**Science checks** (`scripts/`, need network, run by hand):

| Target | Expected movement over a ~1.5-year span | Pass if |
|---|---|---|
| Barnard's Star | 10.4″/yr × Δt ≈ 15″ ≈ 2.5 px | Measured centroid shift from first to last epoch is within ±0.5 px of the expected value |
| A field star in the same frame | 0 | Shift under 0.3 px (if it moves, the alignment is broken, not the sky) |

Print the measured and expected shift side by side. That printout is also a good slide for the pitch.

---

## 8. Timeline

| When | Task | Done when |
|---|---|---|
| 10:30–11:00 | Contract sync. Make the `pyproject.toml` changes. | CI is green on an empty `api/` |
| 11:00–12:00 | Recon (§3) | Answers posted in the team chat |
| 12:00–13:00 | `get_cutouts` + `.npz` cache (§4.1) | **C is unblocked** |
| 13:00–15:00 | `/api/frames?mode=single`: align, σ-normalize, shared stretch, PNGs. Deploy. | **Sync: a real flipbook on the public URL** |
| 15:00–19:00 | Epochs, stacks, `rgb`, `diff`, plus the Barnard's Star check | **Sync: Barnard's Star moves, and the check passes** |
| 19:00–23:00 | Fill `BAD_FLAG_NAMES`, polish `flagged_frac`, tune WISE 0855 in detectors 5–6, pass the 3 unit tests | Every target looks clean |
| 23:00–02:00 | Warm-cache script running; commit the demo snapshot | Demo works with Wi-Fi off |
| 06:00–08:00 | Fixes only. **Freeze at 08:00.** | |

---

## 9. Risks

| Risk | Sign | What to do |
|---|---|---|
| **High-proper-motion targets are off-center.** Barnard's Star has moved about 4.5′ since J2000, which is close to the whole 6′ field. | The star is at the edge or missing | Always use C's current-epoch coordinates from `targets.json`. Coordinates users type in (and `SkyCoord.from_name`) are J2000, so warn in the UI text. |
| Cutouts are big or IRSA is slow | Recon shows more than 2 s per cutout | Pre-warm, then rely on the static snapshot. Lower the default field of view. |
| Only 1–2 epochs | Recon epoch count | RGB with 2 epochs still works (§4.7). Tell C so the pitch can lean on spectra. |
| WISE 0855 isn't visible | Blank `detector=all` stack | Show `detector=5` and `6` only. That's science, not a bug: it is almost invisible at short wavelengths. |
| No time gaps near the poles (R Draconis) | 1 epoch spanning more than 60 days | Chunking rule in §4.4 |
| PNGs come out black | Everything is dark | Check you're on the σ-normalized data with one stretch per response (§4.3, §4.6) |
