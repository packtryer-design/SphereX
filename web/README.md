# web/ (Person B)

Static HTML/JS with no build step and no dependencies. It deploys anywhere that serves files (Netlify Drop, GitHub Pages, Vercel).

## Run locally

```sh
make web            # or: python -m http.server 8080 --directory web
```

Open http://localhost:8080. ES modules don't load from `file://`, so use the server.

## Layout

One full page. The visual design comes later; this fixes the structure.

```
┌ top bar ── Blink102 · field name ──────────────── [Flip] [Stack] ┐
├ rail ─────────┬ stage (image fills it) ──────────┬ info (on click) ┤
│ Fields        │  Flip:  one layer, full size      │ Colors at this  │
│ How to read   │  Stack: all layers fanned out     │ spot: chart +   │
│ Credit        │  click → marker + spectrum        │ plain label     │
├ bottom ───────┴──────────────────────────────────┴─────────────────┤
│ ▶  Blink  [0.85 µm][1.0 µm · Paδ][1.1][1.3 · Paβ][3.3 · PAH][5.0]   │
└────────────────────────────────────────────────────────────────────┘
```

Below 900px the rail becomes a drawer (☰) and the info panel a bottom sheet.

Keys: ← → change layer · space play · b blink · f / s flip or stack · Esc close.

## Adding NASA images

Each field is a folder in `data/` with its images and a `layers.json`:

```json
{
  "id": "my-field",
  "name": "Cygnus X (SPHEREx)",
  "credit": "NASA/JPL-Caltech",
  "layers": [
    { "png": "0.85.jpg", "wavelength_um": 0.85, "feature": null, "tint": "#4f8dff" },
    { "png": "1.0.jpg",  "wavelength_um": 1.0,  "feature": "Paδ", "tint": "#4fe0ff" }
  ]
}
```

Then add `{ "id": "my-field", "name": "…" }` to `data/datasets.json`. Any number of layers works. All images in a field must show the same area at the same size, because clicking reads the same pixel from every layer.

`data/demo-field/` is a generated placeholder (`make demo-data`). Delete it once real images are in.

## Files

| File | What it does |
|---|---|
| `js/api.js` | The only file that knows where data comes from: `data/` now, the Python API later |
| `js/state.js` | `?field=&layer=&view=` in the URL so links can be shared |
| `js/main.js` | Layout wiring: fields, flip/stack, play/blink, click → info panel |
| `js/sample.js` | Reads the brightness at one spot in every layer, in the browser |
| `js/spectrum.js` | SVG spectrum chart with known bands shaded |
| `data/features.json` | Band positions and plain-language glossary. Placeholder until C checks it |

## Later: the backend

Frames from `/api/frames` have the same shape as layers (`png`, `wavelength_um`) plus `mjd`/`epoch`, so they feed the same viewer. The bottom bar then steps through time as well as color. `getFrames`/`getSpectrum` in `js/api.js` are ready for `?api=http://localhost:8000`.

Embed with `?embed=1`, e.g. `<iframe src="https://…/?field=demo-field&view=stack&embed=1" width="900" height="600"></iframe>`.
