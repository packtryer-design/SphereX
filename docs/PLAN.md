# Blink102: Team Plan

> *In 1930, Clyde Tombaugh found Pluto by blinking between two photographic plates. Blink102 blinks the whole sky in 102 colors, so anyone can see what moved and what it's made of.*

NASA Space Apps Challenge Sharjah 2026, SPHEREx challenge.
**Submit by 10:00 on 15 Nov. The hard deadline is 12:00 noon.**

---

## 1. The idea

Tools like Backyard Worlds answer one question: *did it move?* SPHEREx observes in 102 near-infrared colors, and no other all-sky survey does. That lets us answer a second question: *what is it?*

**What a user does:**

1. Type coordinates or a name (for example "Barnard's Star"), or open a shared link.
2. A **flipbook** plays the same patch of sky across each 6-month sweep. Stars stay still and moving objects jump.
3. **Click a moving dot** and its **spectrum** appears, with plain-language labels such as *"water dip → cold brown dwarf"*.
4. Known objects are labeled. **Movers with no catalog match are highlighted** as worth a closer look.

### Features, in priority order

| # | Feature | Priority |
|---|---|---|
| 1 | **Motion in one picture.** Epochs go into the red, green and blue channels of one image. Still stars come out white; moving objects leave a red → green → blue trail. | Must |
| 2 | **Spectral fingerprint.** Click a source to see its spectrum built from the frames, with molecule bands marked. | Must |
| 3 | **Shareable links and embedding.** `?ra=&dec=&fov=&mode=&t=` plus an `<iframe>` example. | Must |
| 4 | **"Is this new?" check.** A ghost marker shows where Gaia predicts each star should be at the frame's date. Optionally, SkyBoT labels known asteroids. | Should |
| 5 | **Time ↔ color switch.** The slider steps through time (shows motion) or through wavelength (shows the spectrum). | Could |
| 6 | Turn the spectrum into sound, and a "Flag it" button for volunteers. | Stretch |

### Spectral labels (C checks every number against a paper before they go on screen)

| Object | What the spectrum shows | Label |
|---|---|---|
| Brown dwarf | Water absorption at 1.4 and 1.9 µm; methane at 1.6, 2.2 and 3.3 µm; bright at 4–5 µm | "Too cold to be a star: water and methane in its air" |
| Comet | CO₂ emission at 4.26 µm, water at ~2.7 µm, CO at 4.67 µm | "Ice turning to gas" |
| Asteroid | Shaped like sunlight, rising at long wavelengths from its own heat | "A rock reflecting sunlight" |
| Star | Smooth curve | "A normal star" |

### Test targets

Barnard's Star, Epsilon Indi B, WISE 0855 (RA 08h55m10.831s, Dec −7°14′42.53″), RW Aurigae, R Draconis. Comet 3I/ATLAS is a bonus demo.

---

## 2. How it fits together

```
Browser (static HTML/JS)                Python API (FastAPI)
 ├─ RA/Dec box + name lookup ─────────► /api/frames?ra=&dec=&fov=&mode=
 ├─ flipbook: slider / play / blink ◄── IRSA SIA query → cutouts → reproject
 ├─ modes: single / epoch / rgb / diff     to common grid → shared asinh stretch → PNG
 ├─ click → spectrum chart ◄─────────── /api/spectrum?ra=&dec=
 ├─ Aladin Lite + Gaia/WISE overlays
 └─ URL state (embeddable)              disk cache keyed by cutout URL
```

### Data facts we rely on

- **Searching by position:** `Irsa.query_sia(pos=(coord, r), collection=['spherex_dr1', 'spherex_qr3'])` from astroquery. The collection names belong in config, so new data releases need no code change. QR3 updates weekly.
- **Cutouts:** append `?center=RA,Dec&size=DEG` to a result's `access_url`. The cutout is a multi-extension FITS file with IMAGE, FLAGS, VARIANCE, ZODI, EPSF and WCS-WAVE.
- **Wavelength of a pixel:** `WCS(header, fobj=hdul, key="W")`, set `.sip = None`, then call `pixel_to_world(x, y)`. It returns the wavelength and bandwidth.
- **Detectors:** 6 detectors cover 0.75–5.0 µm. Each frame covers a gradient of wavelengths, so one spot on the sky is seen about 102 times, once per color, in each sweep. For a sharper image, add together all frames from the same epoch and the same detector.
- **Unverified, so check in the first hour:**
  - the time column (`time_bounds_lower`, probably MJD)
  - the pixel scale (~6.2″)
  - the number of epochs for each target

### API contract (agreed by 11:00, never changed without telling the team)

```jsonc
// GET /api/frames?ra=269.45&dec=4.69&fov=0.1&mode=single|epoch|rgb|diff
{ "target": {"ra": 269.45, "dec": 4.69, "fov": 0.1},
  "frames": [
    {"png": "/cache/abc.png", "mjd": 60812.4, "epoch": 1, "detector": 6,
     "wavelength_um": 4.71, "flagged_frac": 0.02}
  ]}

// GET /api/spectrum?ra=..&dec=..
{ "points": [ {"wavelength_um": 0.78, "flux": 0.012, "err": 0.002, "epoch": 1} ] }
```

---

## 3. Who does what

There are two backend people and one frontend person.

| Person | Role | Folder | Owns |
|---|---|---|---|
| **A** | Backend: imaging | `api/imaging/` | `/api/frames`, cutouts, alignment, image stacking, RGB and difference modes, cache |
| **C** | Backend: science | `api/science/` + `data/` | `/api/spectrum`, Gaia ghosts, SkyBoT, targets, molecule labels, pitch, submission |
| **B** | Frontend and story | `web/` | UI, deploy, explainer copy, README, backup video |

A and C share one FastAPI app (`api/main.py`) and one cutout cache. **A writes the cutout fetcher first (by 13:00)**, and C's spectrum code reuses it. Use short branches and merge into `main` every couple of hours.

### Person A: backend, imaging

Detailed plan: [BACKEND_IMAGING.md](BACKEND_IMAGING.md)

| When | Task | Done when |
|---|---|---|
| 11:00–13:00 | Run the IRSA intro and cutouts notebooks on Barnard's Star. Report frames per epoch and per detector, the time field and the pixel scale. Write `get_cutouts(ra, dec, fov)` with parallel fetching and a disk cache. | **C can call `get_cutouts`** |
| 13:00–15:00 | `/api/frames` in `mode=single`: one shared stretch, then PNGs | A real flipbook shows in the browser |
| 15:00–19:00 | Reproject to a common grid. Add frames per epoch × detector. Add `mode=epoch`, `rgb` and `diff`. | **Barnard's Star moves** |
| 19:00–23:00 | Mask pixels using FLAGS and fill `flagged_frac`. Tune the stretch so WISE 0855 shows up in the stacked images from detectors 5–6. | Every target looks clean |
| Overnight | Script that pre-fills the cache for all targets and 3I/ATLAS. Leave it running. | The demo works without IRSA |
| 06:00–08:00 | Fixes only | |

### Person C: backend, science

| When | Task | Done when |
|---|---|---|
| 11:00–12:00 | `targets.json` with current SIMBAD coordinates. `fixtures/frames.json`. Ask mentors about epochs and moving objects. | A and B are unblocked |
| 12:00–15:00 | `features.json`: molecule wavelengths and labels, each checked against a paper. Prototype the spectrum code in a notebook. | Labels verified |
| 15:00–19:00 | `/api/spectrum`: a pixel value plus the wavelength from the frame's WCS for each cutout from `get_cutouts`. Error bars come from VARIANCE. | WISE 0855 spectrum JSON |
| 19:00–23:00 | `/api/ghosts`: Gaia DR3 proper motions projected to each frame's date. Stretch: `/api/asteroids` via SkyBoT for the comet field. | A ghost sits on Barnard's Star |
| 23:00–02:00 | Write the pitch script. Test every target as a user. | |
| 06:00–09:00 | Rehearse the pitch 3 times with A and B | |
| **09:00–10:00** | **Submit on spaceappschallenge.org and confirm the Google Form** | Confirmation emails received |

### Person B: frontend and story

| When | Task | Done when |
|---|---|---|
| 11:00–13:00 | Page shell (input, viewer, slider, play and blink) working against `fixtures/frames.json`. Read the judging criteria. **Public deploy by 13:00.** | A public URL exists |
| 13:00–15:00 | Frame labels (date · detector · wavelength), mode buttons, URL state | A shared link reopens the same view |
| 15:00–19:00 | Switch to the real API. Add the field-of-view selector and the time ↔ color switch. | Works with real data |
| 19:00–23:00 | Spectrum chart with molecule bands from `features.json`. Write the explainer copy. | Clicking WISE 0855 shows a labeled chart |
| 23:00–02:00 | Aladin Lite panel with Gaia and AllWISE overlays. Ghost markers from `/api/ghosts`. Guided-tour buttons and text. | Guided tour works |
| 06:00–09:00 | Phone layout, `<iframe>` embed example, README with GIF, **record the backup demo video** | |

---

## 4. Check-ins (10 minutes, standing)

| Time | Check |
|---|---|
| **13:00** | Is the public URL live? Do the real epoch counts change the plan? |
| **15:00** | Real-data flipbook works end to end (ugly is fine) |
| **19:00** | Barnard's Star visibly moves. **If it doesn't, C stops the science work and helps A.** |
| **23:00** | Agree what's done and what's cut. Anything not working by now is dropped. |
| **08:00** | **Feature freeze.** Fixes only from here. |
| **10:00** | Submitted |

**Sleep:** all three sleep 02:00–06:00. A starts the cache-warming script before going to sleep.

---

## 5. Pitch (3 minutes)

1. **Hook (20s):** Tombaugh blinked 2 plates and found Pluto. SPHEREx records more than a billion objects in 102 colors, with a new sweep every 6 months. No single person can sift through that.
2. **Problem (20s):** today, looking at SPHEREx data takes Python, FITS files and an astronomy degree.
3. **Live demo (90s):**
   - Open a shared link to Barnard's Star: it jumps.
   - Switch to motion in one picture (RGB mode): a rainbow trail.
   - Open WISE 0855 and click it: the spectrum shows water and methane.
   - Show the Gaia ghost marker matching the star.
4. **Why it matters (30s):** anyone can use it, it updates weekly from IRSA, and it can be embedded anywhere. Volunteers found most known brown dwarfs and comets.
5. **Next (20s):** scan the whole sky automatically for unexplained movers, and add a volunteer flagging loop.

Have a backup screen recording of exactly this path.

---

## 6. Risks

- **About 300 cutouts per target.** Fetch in parallel, cache them, and pre-fill the cache for the demo targets.
- **WISE 0855 is very faint at short wavelengths.** It may only appear in the stacked images from detectors 5–6. If its spectrum is too weak, use Barnard's Star or the comet for the spectrum demo.
- **Fewer epochs than expected.** Check in the first hour. If coverage is thin, lead with Barnard's Star.
- **No discovery claims.** "Candidate for review" is the strongest wording we use.

## 7. Links

- IRSA SPHEREx: https://irsa.ipac.caltech.edu/Missions/spherex.html
- Archive docs: https://caltech-ipac.github.io/spherex-archive-documentation
- Tutorials: https://caltech-ipac.github.io/irsa-tutorials/spherex-intro/ · https://caltech-ipac.github.io/irsa-tutorials/spherex-cutouts/
- Cutout tool: https://irsa.ipac.caltech.edu/data/SPHEREx/docs/cutout_tool.html
- Explanatory Supplement: https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf
- Comet 3I/ATLAS: https://irsa.ipac.caltech.edu/data/SPHEREx/docs/comet3iatlas/index.html
- Aladin Lite: https://github.com/cds-astro/aladin-lite · reproject: https://github.com/astropy/reproject
- Submission guide: https://www.spaceappschallenge.org/resources/project-submission-guide/
