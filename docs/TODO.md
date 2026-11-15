# SpotX: To-Do by Person

Status at **14 Nov, 16:30**. Built from the reviews of PRs #13 (frontend) and #15 (science v2), and a click-through of the site in a real browser.

**Remaining deadlines:** 19:00 check-in · 23:00 cut list · **08:00 feature freeze** · **10:00 submit** (hard deadline 12:00).

Every task has a "done when" so anyone can tick it off. Open a PR for every change. Pushes straight to `main` skip CI.

---

## 🧭 Team (decide at the 19:00 check-in)

| # | Task | Why | Done when |
|---|---|---|---|
| T1 | ✅ **Decided: lead with Planet X, show SpotX as the tool, end with "What's next".** (1) Story 3, Planet X (`/track.html`, PR #19): Pluto tracked against JPL Horizons, the blind search finds Pluto, a simulated planet appears only when stacked. (2) Story 1, the SpotX explorer: "anyone can do this for any star", on Barnard's Star, covering the challenge's required features and test targets. (3) Story 2 (SPHEREx Watch, classroom lab) is **not built**; it's the "What's next?" slide, with a deeper planet search. | The pitch and demo path follow from it. `PITCH.md` and `SUBMISSION.md` still describe the older pitch (C4). | Done |
| T2 | ⏳ **Exact demo path:** decided while preparing the pitch, following T1's order (Pluto → blind search → planted planet → Barnard's Star in SpotX) | Everything on the path must be pre-warmed and rehearsed | The path is listed in `PITCH.md` and every object on it is warmed |
| T3 | ✅ **CodeQL:** the repo is public, and CodeQL passes on PRs. Close Copilot's draft PR #8, which is no longer needed. | — | Done |
| T4 | ✅ **Team brief:** no change needed. It never named the project ("Blink102" never appeared; only the phrases "blink compare" and "imaged 102 times"). | — | Done |

---

## 🅰️ Person A: backend imaging and infrastructure

| # | Task | Done when |
|---|---|---|
| A1 | ✅ **Spectra warming:** `warm_cache.py` also builds `/api/spectrum` for the science targets. Each spectrum uses its own ~4 MB cutouts, so a cold one on stage meant ~350 slow downloads. Spectra for the 5 science targets are being built on A's machine now. | Done in code. Spectra finished: see A2 |
| A2 | ⏳ **Finish the cache warm** (running on A's machine: demo objects first, then all 45). IRSA is slow, and Orion had 2 frames fail after 6 retries; they get retried on the next run. | Log shows `=== ALL DONE ===` and every demo object opens instantly |
| A3 | 🟡 **Deploy publicly. Ready, needs an account login.** The `Dockerfile` runs API + site in one container on any host. Steps: **(1)** create a free *Web Service* on Render (or Fly.io / Cloud Run / HF Spaces) from this repo; it detects the `Dockerfile`; **(2)** no settings needed (`$PORT` is honoured, cache goes to `/tmp`); **(3)** open `<url>/?o=barnards-star`. Not built in Docker yet (Docker Desktop was off), but the same command was tested locally. | A public URL opens Barnard's Star |
| A4 | 🟡 **Demo snapshot. Mechanism done and tested**: the server copies `cache/demo/` into its cache at startup, and a fresh server with an empty cache served Barnard's Star in ~25 ms with zero downloads. **Still to do:** once A2 finishes, run `python scripts/demo_snapshot.py` and commit `cache/demo/`. | `cache/demo/` holds every demo object, committed |
| A5 | *Only if T1 picks it:* SPHEREx Watch RSS feed (~3 h) | `/api/watch.xml?ra=&dec=` opens in a feed reader |
| A6 | *Only if the comet is in the demo:* 3I/ATLAS needs a position per frame date from JPL Horizons. It's skipped today. | Comet frames line up on the comet |

---

## 🅱️ Person B: frontend

| # | Task | Done when |
|---|---|---|
| B1 | ✅ **Wire C's spectrum into the Spectrum tab.** The site only calls `/api/surface-spectrum` (the nebula method), so C's PSF photometry, WISE check and saturation note never show. Stars and brown dwarfs should use `/api/spectrum?ra=&dec=&target=<id>`; nebulae stay on `surface-spectrum`. | Barnard's Star shows C's spectrum with its saturation note, and WISE 0855 shows its WISE W2 check |
| B2 | ✅ **One set of coordinates per object.** The catalog's Barnard's Star (Dec 4.76964) is about 5″ from C's `targets.json` (4.7682), so they're cached separately and `?o=barnards-star` isn't warm. For the science objects, use the `ra_2026`/`dec_2026` from `data/targets.json` in `objects.json`. **Also add the 4 missing science targets** (eps-indi-b, wise-0855, rw-aur, r-dra); see [SPECTRUM_API.md](SPECTRUM_API.md). | `?o=barnards-star` opens instantly after warming, and `?o=wise-0855` opens |
| B3 | ✅ Show a clear "first load can take minutes" state on the Spectrum tab, as the Explore tab does | No blank chart without an explanation |
| B4 | ✅ Add a favicon (the only 404 in the browser console) | Console is clean |
| B5 | ✅ Phone layout check, `<iframe>` embed example (`/embed.html`) | Works at phone width |
| B6 | ✅ *Recorded: [`docs/media/spotx-demo.mp4`](media/spotx-demo.mp4) (40 s) + GIF in the README, linked in `SUBMISSION.md`. Still to do by a human: upload it (YouTube unlisted / Drive) and paste the link. Barnard's Star's spectrum step is left out until that spectrum is warm on the recording machine; re-record with `python scripts/record_demo.py`.* README with a GIF of the demo path, plus **a backup screen recording of the demo** | Video saved and linked in `SUBMISSION.md` |

**Done in PR #18 (C, on B's files):** stars, brown dwarfs and the young/variable stars now use `/api/spectrum` (PSF fit, saturation note, WISE W2 check, per-band status: seen / not clear / too faint / not measured). Nebulae stay on `surface-spectrum`. `objects.json` takes the 2026 positions from `data/targets.json` and now lists all 5 science targets. Point spectra start as soon as the visit list arrives instead of waiting for the images. Also fixed (A's file): two requests fetching the same cutout at once crashed on Windows (`WinError 32`) in `api/imaging/cutouts.py`.

**B's branch, merged with #18 (15 Nov):** B1–B4 were also built on B's branch at the same time. The merge keeps one version of each: C's `api.js` helper, kinds text and early start for star spectra; B's Spectrum-tab layout (separate note boxes for saturation, WISE check and nearby stars, the binned spectrum line, seen/not-clear band shading with paper references, a timer while loading) and favicon file; and one science-target path in `build_objects.py` (SIMBAD aliases, full-precision 2026 positions, plus `spectrum: "point"`). B also fixed two bugs found by clicking through in a real browser: every click on the image re-ran the current view (it would stop playback), and search ranked constellation matches above object names.

**Already verified in a browser:** Sequence, Blink, Side by side, Swipe, Difference, Color-time, Observations and About all work on Barnard's Star. Difference and Color-time clearly show its motion.

---

## 🅲 Person C: science backend, pitch and submission

| # | Task | Done when |
|---|---|---|
| C1 | ✅ Field guide written: [SPECTRUM_API.md](SPECTRUM_API.md). **Help B with B1:** tell B which fields from `/api/spectrum` to show and how (`saturation_note`, `w2_check`, `blends`, binned points) | B1 merged |
| C2 | ✅ Add `scipy` to `dependencies` in `pyproject.toml`. `psf.py` imports it, and it only works today because `reproject` happens to install it. | Listed in `pyproject.toml` |
| C3 | ✅ Add a sentence to the docs: the ePSF calibration files come from QR3 and are also applied to DR1 frames | Noted in `SUBMISSION.md` or the code |
| C4 | **Rewrite `PITCH.md` and `SUBMISSION.md` to the story from T1.** Keep the strong honest results: Barnard's Star motion, the WISE 0855 W2 agreement within 14%, saturation handled openly. | Pitch matches the site |
| C5 | **Rehearse the pitch 3 times with A and B** (06:00–09:00) | Done 3 times, timed |
| C6 | **Submit on spaceappschallenge.org and confirm the Google Form** (09:00–10:00) | Confirmation emails received |

---

## 🔧 Fixed this evening (PRs #17 and #18)

| Item | Owner | What was fixed | PR |
|---|---|---|---|
| B1 | B (done by C) | Stars, brown dwarfs, young and variable stars use `/api/spectrum`: PSF fit, saturation note, WISE W2 check. Shaded bands come from the API's own features at their real wavelength ranges, each marked seen / not clear / too faint to tell / not measured. Nebulae stay on `surface-spectrum`. | #18 |
| B2 | B (done by C) | `objects.json` uses the 2026 positions from `data/targets.json`, so the warmed cache is hit. All 5 science targets listed (new kinds: brown dwarf, young star, variable star). | #18 |
| B3 | B (done by C) | Spectrum tab shows a waiting message instead of a blank chart. Star spectra start as soon as the visit list arrives instead of waiting for the images. | #18 |
| B4 | B (done by C) | Favicon added; browser console clean. | #18 |
| Bug | A (found by C) | Two requests fetching the same cutout at once crashed on Windows (`PermissionError WinError 32`). Each download now uses its own temp file in `api/imaging/cutouts.py`. | #18 |
| C1 | C | Field guide for the spectrum API: [SPECTRUM_API.md](SPECTRUM_API.md). | #17 |
| C2 | C | `scipy` listed in `pyproject.toml`. | #17 |
| C3 | C | QR3 ePSF note in `SUBMISSION.md` and `psf.py`. | #17 |
| Doc | C | WISE 0855 offset corrected: about 3.5′ since J2000, not 1.5′. | #17 |

Merge #17 first: #18 is built on it.

## ⏭️ Still open, by owner (none of these can be fixed in code)

| Owner | Items | Why it isn't code |
|---|---|---|
| Team | T2 | The demo path, decided while preparing the pitch |
| A | A2, A3, A4 | A2 runs on A's machine; A3 needs a hosting account login; A4 waits on A2. A5/A6 only if T1/T2 pick them. |
| B | B5, B6 | Phone check, embed example, README GIF and the backup screen recording |
| C | C4, C5, C6 | C4 can start (T1 decided); C5 is rehearsal with A and B; C6 is the submission |

---

## ✅ Done today (for reference)

- Imaging pipeline. Barnard's Star motion verified: 1.52 px measured vs 1.66 px expected.
- Wavelength-matched difference (PR #12), the warm-cache fixes (#11) and CI lint fixes (#10).
- Frontend with 6 views and 4 tabs (#13). Science v2: PSF photometry, blend fitting, WISE check (#15).
- Competitor review and ideas ([IDEAS.md](IDEAS.md)).
