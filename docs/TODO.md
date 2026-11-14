# Blink: To-Do by Person

Status at **14 Nov, 16:30**. Built from the reviews of PRs #13 (frontend) and #15 (science v2), and a click-through of the site in a real browser.

**Remaining deadlines:** 19:00 check-in · 23:00 cut list · **08:00 feature freeze** · **10:00 submit** (hard deadline 12:00).

Every task has a "done when" so anyone can tick it off. Open a PR for every change. Pushes straight to `main` skip CI.

---

## 🧭 Team (decide at the 19:00 check-in)

| # | Task | Why | Done when |
|---|---|---|---|
| T1 | **Agree on one story.** "Blink: nebulae over time" (what's built) vs SPHEREx Watch + classroom lab ([IDEAS.md](IDEAS.md)) | The pitch, demo path and remaining features depend on it. `PITCH.md` and `SUBMISSION.md` still describe the older wavelength-first pitch. | One sentence agreed and written at the top of `PITCH.md` |
| T2 | **Agree the 3-step demo path** (which objects, which views, in what order) | Everything on the path must be pre-warmed and rehearsed | The path is listed in `PITCH.md` and every object on it is warmed |
| T3 | **CodeQL check:** make the repo public and enable code scanning, *or* delete `.github/workflows/codeql.yml` and close PR #8 | It fails because code scanning isn't enabled on a private repo. It's a settings question, not a code bug. | No red ❌ on PRs |
| T4 | Update the team brief (`SPHEREx_Team_Brief.docx`) to the final name | It still says Blink102 | Name matches the site |

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
| B2 | ✅ **One set of coordinates per object.** The catalog's Barnard's Star (Dec 4.76964) is about 5″ from C's `targets.json` (4.7682), so they're cached separately and `?o=barnards-star` isn't warm. For the science objects, use the `ra_2026`/`dec_2026` from `data/targets.json` in `objects.json`. | `?o=barnards-star` opens instantly after warming |
| B3 | ✅ Show a clear "first load can take minutes" state on the Spectrum tab, as the Explore tab does | No blank chart without an explanation |
| B4 | ✅ Add a favicon (the only 404 in the browser console) | Console is clean |
| B5 | ✅ Phone layout check, `<iframe>` embed example (`/embed.html`) | Works at phone width |
| B6 | 🟡 *Recorder done (`scripts/record_demo.py`); video + GIF follow once Barnard's Star and Orion are warm.* README with a GIF of the demo path, plus **a backup screen recording of the demo** | Video saved and linked in `SUBMISSION.md` |

**Already verified in a browser:** Sequence, Blink, Side by side, Swipe, Difference, Color-time, Observations and About all work on Barnard's Star. Difference and Color-time clearly show its motion.

---

## 🅲 Person C: science backend, pitch and submission

| # | Task | Done when |
|---|---|---|
| C1 | **Help B with B1:** tell B which fields from `/api/spectrum` to show and how (`saturation_note`, `w2_check`, `blends`, binned points) | B1 merged |
| C2 | Add `scipy` to `dependencies` in `pyproject.toml`. `psf.py` imports it, and it only works today because `reproject` happens to install it. | Listed in `pyproject.toml` |
| C3 | Add a sentence to the docs: the ePSF calibration files come from QR3 and are also applied to DR1 frames | Noted in `SUBMISSION.md` or the code |
| C4 | **Rewrite `PITCH.md` and `SUBMISSION.md` to the story from T1.** Keep the strong honest results: Barnard's Star motion, the WISE 0855 W2 agreement within 14%, saturation handled openly. | Pitch matches the site |
| C5 | **Rehearse the pitch 3 times with A and B** (06:00–09:00) | Done 3 times, timed |
| C6 | **Submit on spaceappschallenge.org and confirm the Google Form** (09:00–10:00) | Confirmation emails received |

---

## ✅ Done today (for reference)

- Imaging pipeline. Barnard's Star motion verified: 1.52 px measured vs 1.66 px expected.
- Wavelength-matched difference (PR #12), the warm-cache fixes (#11) and CI lint fixes (#10).
- Frontend with 6 views and 4 tabs (#13). Science v2: PSF photometry, blend fitting, WISE check (#15).
- Competitor review and ideas ([IDEAS.md](IDEAS.md)).
