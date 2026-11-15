# web/

The SpotX front end: static HTML, CSS and ES modules, with no build step and no dependencies.

## Run it

```sh
make serve     # API + front end on http://localhost:8000
```

`make web` serves the front end alone on port 8080. Search, the catalog and the About tab work there, but images and spectra need the API. To point a static deploy at an API elsewhere, add `?api=https://your-api-host`.

## What the user sees

```
┌ SpotX  [ Search nebulae: Orion, Ring, NGC 7293… ]                         ┐
├ Orion Nebula  Emission nebula in Orion    Explore │ Observations │ Spectrum │ About ┤
│                                                                           │
│                 the image, as large as the screen allows                  │
│                                                                           │
│ 6–17 Sep 2025                                         [legend / caveat]   │
│ Visit 1 of 3 · 123 exposures · all 6 detectors                            │
├───────────────────────────────────────────────────────────────────────────┤
│ (Sequence) Blink  Side by side  Swipe  Difference  Colour-time             │
│ ▶   ●───────── 6 months ─────────●───────── 6 months ─────────●            │
│     Sep 2025                    Mar 2026                    Sep 2026       │
└───────────────────────────────────────────────────────────────────────────┘
```

- **Home** lists every catalog object by kind, with how many SPHEREx visits each has.
- **Search** matches names, catalog ids (M 42, NGC 7293) and constellations instantly. "Look up …" finds anything else by name through SIMBAD or NED.
- **Explore** is the viewer. The timeline places visits by their real dates, so the gaps are true to scale.
  - **Sequence** crossfades from visit to visit. Use ▶ to play, or ← → to step.
  - **Blink** flips quickly between visits A and B.
  - **Side by side** and **Swipe** show A and B together. Drag the divider in Swipe.
  - **Difference** shows B minus A, computed by the API only over the detectors both visits share.
  - **Colour-time** puts three visits in red, green and blue. Anything that is the same in all three comes out white.
  - Click any spot to see its brightness at every visit.
- **Observations** shows a card for each visit: dates, exposures, which of the six detectors were used, and the gap since the previous visit. It ends with a short guide to telling real change from artifacts.
- **Spectrum** has one dot per exposure, coloured by visit. The method depends on the object:
  - **Stars and brown dwarfs** (catalog objects with a `target_id`) use Person C's `/api/spectrum`: PSF photometry in mJy, a binned spectrum line, molecule bands marked *seen* only at 3σ or more, each with its paper reference, plus the saturation note, the WISE W2 cross-check and nearby Gaia stars.
  - **Nebulae** use `/api/surface-spectrum` (surface brightness), with hydrogen and dust lines shaded for reference.
  - While it loads, the chart says what it's waiting for, with a timer, because a cold spectrum can take minutes.
- **About** gives what kind of object it is, what to expect over time, its position, size and catalog names, with links to SIMBAD and IRSA.

The URL always holds the view (`?o=orion&tab=explore&view=blink&a=1&b=3`), so any view can be shared. Positions found by name lookup use `?ra=&dec=&fov=&name=`.

**Embedding:** add `&embed=1` to hide the header and tabs. [`embed.html`](embed.html) (`/embed.html` on the running site) shows a live example and the code to copy:

```html
<iframe src="https://<your-blink-host>/?o=barnards-star&view=rgb&embed=1"
        width="900" height="600" style="border:0" loading="lazy"
        title="SpotX: SPHEREx visits"></iframe>
```

## Honest data, by design

- **Dates are real.** They come from IRSA (`/api/visits`). Most of the sky gets a visit about every six months. Near the ecliptic poles SPHEREx passes almost monthly, but each pass may use only some detectors.
- **Like-for-like comparisons.** Every visit is reprojected onto one grid and shares one brightness scale. When two visits used different detectors, the viewer says so, because the difference may be colour rather than change.
- **Nothing is invented.** If SPHEREx hasn't observed a position, or only caught it at a detector edge, the page says so instead of showing anything.

## Files

| File | What it does |
|---|---|
| `js/main.js` | App wiring: home, opening objects, tabs, views, timeline, click-a-spot, tab contents |
| `js/api.js` | The only file that knows where data comes from. Finds the API at runtime: `?api=`, else this site, else the address `scripts/host.py` publishes (docs/HOSTING.md) |
| `js/state.js` | View state ↔ URL |
| `js/viewer.js` | Crossfading image panes; pixel → sky position |
| `js/search.js` | Search box (catalog matches + name lookup) |
| `js/spectrum.js` | SVG charts: spectrum and brightness over time |
| `js/sample.js` | Reads brightness at one spot from each visit's image, in the browser |
| `js/kinds.js` | Plain-language text for each kind of object; SPHEREx detector ranges |
| `js/time.js` | MJD → readable dates and gaps |
| `embed.html` | How to embed SpotX, with a live example |
| `favicon.svg` | Tab icon |
| `data/objects.json` | The catalog. Built by `make objects` from SIMBAD + IRSA, so don't edit it by hand. To add an object, add a line to `OBJECTS` in `scripts/build_objects.py`. Science targets from `data/targets.json` are included automatically, at their `ra_2026`/`dec_2026` positions, so the site and `/api/spectrum` share one cache entry |
| `data/features.json` | Reference lines shaded on the spectrum (laboratory wavelengths) |

## API used

| Endpoint | Returns |
|---|---|
| `GET /api/visits?ra=&dec=` | Real visit dates, exposure counts and detectors. Fast, no image downloads |
| `GET /api/frames?ra=&dec=&fov=&mode=epoch` | One aligned PNG per visit |
| `GET /api/frames?...&mode=diff&ref=N` | Each visit minus visit N, over shared detectors |
| `GET /api/frames?...&mode=rgb` | Three visits as one colour image |
| `GET /api/spectrum?ra=&dec=&target=` | Person C's point-source spectrum (stars, brown dwarfs) |
| `GET /api/surface-spectrum?ra=&dec=&field_ra=&field_dec=&fov=` | Surface brightness, one point per exposure (wavelength, flux, error, date). Right for nebulae. Person C's `/api/spectrum` does aperture photometry for stars |
| `GET /api/resolve?name=` | Coordinates for a name, from SIMBAD or NED |

Frames carry `detectors`, `mjd_start` and `mjd_end` (and `ref_epoch` in diff mode, `epochs` in rgb mode) on top of the original contract in [docs/PLAN.md](../docs/PLAN.md).
