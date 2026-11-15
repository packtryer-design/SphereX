# SpotX — 3-minute pitch

Team **Ballers**: Amro Taha, Mountacire Billah, Husain Ali. NASA Space Apps 2026 (Sharjah), challenge **Planet X and SPHEREx**.

Rules: **no discovery claims.** The strongest wording we use is "candidate for review". The planted planet is simulated, a test of the method.

## The story in one line

Pluto was found in 1930 by flipping between two photos. NASA now photographs the whole sky every six months, but the public can't flip through those photos. We built the flipbook, and it already finds Pluto by itself.

The talk opens and closes on the same idea (flipping between photos to find planets, then and now). The demo is the proof, and the numbers show it's real science.

## Script (7 slides)

| Time | Slide | What to say |
|---|---|---|
| 0:00–0:20 | 1 Title, 2 Problem | "In 1930, Pluto was found by flipping between two photos: stars stay still, planets move. Today NASA's SPHEREx photographs the whole sky in 102 colours, 550 million stars and galaxies. But only astronomers can open the files." |
| 0:20–0:40 | 3 Solution | "We're team Ballers. SpotX is a flipbook for SPHEREx: anything that moves jumps out. Any browser, no login." |
| 0:40–2:10 | 5 Demo (Planet X search) | **Live demo**, see [Live demo](#live-demo-90-s) below. |
| 2:10–2:45 | 4 NASA data, 6 Impact | "All real NASA data: SPHEREx images, JPL orbits, WISE stars. Uranus lands 0.3 pixels from JPL's prediction. That's 2.7 million citizen scientists who could use this today." |
| 2:45–3:00 | 7 Next steps | "Next: scan the whole sky for unexplained movers, and let volunteers flag them. We didn't find Planet X; we built the tool to look. Thank you." Then stop. |

Numbers and where they come from:
- 450M+ galaxies and 100M+ stars: NASA JPL SPHEREx mission page.
- 0.3 px (Uranus), 0.8 px (Neptune) from JPL: `scripts/check_track.py`.
- Pluto found blind at 45× the noise; test planet recovered down to 45× fainter than Pluto: `web/snapshot/pluto/planetx.json`.
- 2.7M Zooniverse volunteers (March 2025, Wikipedia). 125K+ Backyard Worlds volunteers (Zenodo record, undated; 2017 reports say 20–42K, so check backyardworlds.org before quoting).

## Live demo (90 s)

### Before going on stage

- Open three tabs, in this order, on the Netlify site or a local copy (`python -m http.server 8080 -d web`, which needs no internet for the data):
  1. `/track.html?body=pluto`
  2. `/?o=barnards-star&view=rgb`
  3. `/?o=wise-0855&tab=spectrum`
- Load each tab once so nothing is still loading on stage. Zoom 100%, full screen (F11).
- Have the backup video (below) ready on the laptop, in case the Wi-Fi or a page fails.

### Clicks and lines

| Time | Do | Say |
|---|---|---|
| 0:40 | Tab 1, press play | "This is Pluto in real SPHEREx images. The circle is where NASA JPL says it should be, placed without looking at the images. Watch it land there." |
| 0:55 | Click Neptune, then Uranus | "Same for Neptune and Uranus." |
| 1:05 | Click Pluto, scroll to "Could SPHEREx find a new planet?" | "A planet far beyond Pluto would be too faint for any single image." |
| 1:15 | Point at the three panels, left to right | "One image: nothing. Stacked: a smear. Shifted along its path: found. It found Pluto without being told where to look." |
| 1:35 | Point at the result line | "We planted a test planet in the real images, and it found it down to 45 times fainter than Pluto. That's how you'd hunt for Planet X." |
| 1:50 | Tab 2 | "It works on any object. Three visits in red, green and blue: Barnard's Star moves and leaves a rainbow." |
| 2:00 | Tab 3 | "And its colours tell you what something is made of: water and methane in this brown dwarf." |
| 2:10 | Back to the slides | Go into NASA data and Impact. |

- Rehearse with a stopwatch. Running long: cut tab 3 first, then Neptune and Uranus.
- Say "test planet", never "we found a planet".
- If something hangs, don't wait: say "here's the recording" and play the backup video.

## Submission video and stage backup (30 s, English subtitles)

The submission needs a 30-second subtitled demo video. The same file is the backup if the live demo fails.

### Shot list

The Planet X search is the centre: 12 of the 30 seconds. Each line is one subtitle. Open the links in this order.

| Time | Page | Action | Subtitle |
|---|---|---|---|
| 0–3 s | `/` | Hold on the home page | NASA SPHEREx photographs the whole sky every six months. |
| 3–10 s | `/track.html?body=pluto` | Press play, "Show predicted position" on | Pluto drifts across still stars and lands in NASA JPL's predicted circle. |
| 10–16 s | same page | Scroll slowly to "Could SPHEREx find a new planet?" | Planet X search: a far planet is too faint for any single image. |
| 16–22 s | same page | Hold on the three panels (one image, stacked, shifted) | Shift 46 images along its path: a test planet 45× fainter than Pluto appears. |
| 22–26 s | `/?o=barnards-star&view=rgb` | Hold on colour-time | Works on any object: a moving star leaves a rainbow. |
| 26–30 s | `/?o=wise-0855&tab=spectrum` | Hold on the chart | Its light shows water and methane. All real NASA data. |

Neptune and Uranus are left out of the video for time; click them live if the demo runs long enough.

### Recording it

1. **Serve the site.** Use the public Netlify site, or run it locally from the snapshot (instant, no API, no downloads):
   ```bash
   python -m http.server 8080 -d web
   ```
   Then open http://localhost:8080. Don't record while `scripts/build_snapshot.py` is running: it deletes `web/snapshot/` first.
2. **Set up the browser.** Chrome or Edge, zoom 100%, full screen (F11) on a 1920×1080 display. Open every page in the shot list once before recording, so nothing is still loading on camera.
3. **Record.** Windows 11: Snipping Tool's screen recorder (Win+Shift+R, drag over the screen) or Xbox Game Bar (Win+Alt+R). macOS: Cmd+Shift+5. Follow the shot list slowly; record 2–3 takes and keep the best. Aim for about 35 s raw so there's room to trim.
4. **Edit and add subtitles.** In Clipchamp (built into Windows 11) or any editor: trim to 30 s, add one text caption per shot-list row (bottom of the frame, white on a dark band, at least 4 s each), export at 1080p.
5. **Back it up.** Upload as unlisted YouTube or public Drive and put the link in `docs/SUBMISSION.md`. Keep the file on the presenting laptop as the stage backup.

The old automated recorder, `scripts/record_demo.py`, follows the earlier Barnard's Star demo path, not this story.

## Q&A crib

| Question | Answer |
|---|---|
| Is the spectrum calibrated? | Fluxes are PSF fits with SPHEREx's official ePSFs on IRSA's calibrated, zodi-subtracted images (MJy/sr → mJy); aperture photometry only where a fit fails. A 3 % systematic floor is added to every error bar. Good for shape; absolute level ~10 %. Each spectrum is cross-checked against AllWISE W2 (4.6 µm): WISE 0855 agrees within 14 %. |
| How do you know it's water? | Band depth vs a power-law continuum fitted either side, ≥ 3σ. Band edges from Cushing 2005, Burgasser 2006 (cited in-app). For WISE 0855, SPHEREx sees the *effect* (light only escaping at 4–5 µm) rather than individual dips — it is ~25th mag below 2 µm. |
| Isn't WISE 0855 blended? | Yes — a G=16.3 star sits 7″ away, 1 pixel. We fit both stars together with the SPHEREx PSF, so the neighbour's light is split off (254 of 258 points). Before that, the "brown dwarf" showed 0.9 mJy below 2 µm — all of it the neighbour. After: zero below 4 µm, ~0.5 mJy at 4.4–5 µm, consistent with WISE W2. |
| How do you know the planet tracking is right? | JPL Horizons predicts each position without looking at our images; `scripts/check_track.py` measures where the planet actually is. Uranus is 0.3 px off, Neptune 0.8 px, and the spot goes dark once the planet has moved on. |
| Did you find Planet X? | No. The planted planet is simulated, to test the method on real frames. Real Planet X candidates would be too faint/slow for a 6″ pixel in one year; the same shift-and-stack logic is how a wide survey would look. |
| How do you check asteroids? | IMCCE SkyBoT at each frame time; next step is cross-checking with JPL SBIdent. |
| Data source? | SPHEREx DR1 / quick release spectral images, IRSA SIA + cutout service; JPL Horizons for planet positions; Gaia DR3 + CatWISE2020 for ghosts (CatWISE sees cold brown dwarfs Gaia can't); AllWISE W2 as flux sanity check. |
