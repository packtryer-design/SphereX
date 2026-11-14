# `/api/spectrum`: what to show (for B1)

Use it for **stars, brown dwarfs and other point sources** (everything in `data/targets.json`). Nebulae stay on `/api/surface-spectrum`.

```
GET /api/spectrum?ra=<ra_2026>&dec=<dec_2026>&target=<id>
```

Use `ra_2026`/`dec_2026` from `data/targets.json`. Other coordinates make a different cache key, so the request won't be warm (see B2). A cold request downloads hundreds of cutouts and can take minutes, so show a loading message (B3).

## Fields

| Field | Example (WISE 0855) | Show it how |
|---|---|---|
| `points[]` | `{wavelength_um, flux, err, mjd, method, fit_ql, epoch}` | Same scatter plot as now. `flux`/`err` are in **mJy** (`units.flux`), not MJy/sr. `mjd` colours by visit, as today. |
| `binned[]` | `{wavelength_um, flux, err, n}` | Optional thick line through the points: the clean spectrum. |
| `features` | same shape as surface-spectrum (`profile`, `label`, `plain`, `bands[]`, `caveat`) | The band shading and labels you already draw. |
| `saturation_note` | `null`, or "Too bright for SPHEREx: …" | **If not null, show it above the chart.** R Dra has 0 points and only this note; Barnard's Star has 36 points plus the note. |
| `w2_check` | `{wise_mJy: 0.567, spherex_mJy: 0.486, ratio: 0.857}` | One line under the chart: "WISE check at 4.6 µm: SPHEREx 0.49 mJy vs WISE 0.57 mJy (86%)". It can be `null`; then hide the line. If `wise_saturated` is true, add "(WISE saturated)". |
| `blends[]` | `{source_id, g_mag, sep_arcsec, fitted}` | If any: "Nearby star G=16.3 at 7.9″: fitted out" (`fitted: true`), or "…: too close to separate, may add light" (`fitted: false`). |
| `n_frames`, `n_saturated`, `n_failed` | 258, 4, 0 | Small print: "254 of 258 frames used". |
| `photometry` | `{psf: 254, aperture: 0, sys_floor: 0.03}` | Optional: "PSF-fitted, 3% calibration floor". |

## Catalog gap (part of B2)

`web/data/objects.json` has only **barnards-star** of the 6 science targets. `eps-indi-b`, `wise-0855`, `rw-aur` and `r-dra` are missing, so `?o=wise-0855` doesn't open. Searching by name doesn't help either: it gives SIMBAD's J2000 position, and WISE 0855 has moved about 1.5′ since then, so the spectrum would miss it. Add the 4 entries using `ra_2026`/`dec_2026` from `data/targets.json`. `3i-atlas` has no fixed position (A6).

## Quick checks once wired

- WISE 0855: about 254 points, the 4.4 µm window marked seen, and the WISE line showing 86%.
- Barnard's Star: points, the saturation note, and a WISE line.
- R Dra: no chart, only the saturation note, and no JS error.
