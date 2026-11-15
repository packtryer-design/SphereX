# Space Apps 2026 submission — Blink

Paste-ready text for the spaceappschallenge.org project page. **A human on the team must submit** (needs the team account). Deadline: submit by **10:00, 15 Nov**; hard cut-off 12:00.

## Checklist (09:00–10:00)

- [ ] Live demo URL works on a phone (B)
- [ ] Backup demo video uploaded (YouTube unlisted or Drive, public link) (B). Recorded: [`docs/media/blink-demo.mp4`](media/blink-demo.mp4) (40 s). Needs uploading by a team member
- [ ] Repo public (team decision). README has the GIF + run instructions (B, done)
- [ ] All `[fill in]` fields below are filled in
- [ ] Project page submitted on spaceappschallenge.org, challenge **"Planet X and SPHEREx"**
- [ ] Local-event Google Form confirmed (Sharjah)
- [ ] Both confirmation emails received — screenshot them into the team chat

---

## Project name

Blink

## High-level summary (≤ 150 words)

Blink is a browser-based blink comparator for NASA's SPHEREx all-sky infrared survey. Pick any spot on the sky and it pulls SPHEREx images live from IRSA, aligns them, and flips through the visits so anything that moves jumps out — the same technique Clyde Tombaugh used to find Pluto. One click turns the 102 SPHEREx colours into a spectrum, and the app marks molecules like water, methane and CO₂ only when the data shows them at 3σ, citing the paper behind each label. A "ghost" marker shows where Gaia predicts each known star should be on that date, and SkyBoT labels known asteroids, so a moving dot that matches nothing becomes a candidate for human review. No install, no account, shareable links.

## Link to project / demo

- Demo: `[fill in live URL]`
- Video: `[fill in public link after uploading]`. File: [`docs/media/blink-demo.mp4`](media/blink-demo.mp4), recorded from the live app on real data by `scripts/record_demo.py`
- Code: https://github.com/packtryer-design/SphereX

## Project details

**What it does.** Three views of the same SPHEREx data:
1. *Blink*: single frames, per-epoch stacks, an RGB "rainbow trail" (three epochs in red/green/blue — still stars go white, movers leave colour), and difference images.
2. *Spectrum*: every SPHEREx frame sees a source at one wavelength, so PSF photometry (SPHEREx ePSFs, fitting nearby Gaia stars at the same time) on all frames covering it gives its 0.75–5 µm spectrum, with a 3 % systematic error floor. Bands are measured against a power-law continuum and labelled "seen" only at ≥3σ. The 4.2–5.0 µm flux is cross-checked against AllWISE W2 (WISE 0855: SPHEREx 0.49 mJy vs WISE 0.57 mJy).
3. *Is this new?*: Gaia DR3 and CatWISE2020 (infrared, finds cold brown dwarfs Gaia misses) positions propagated with proper motion to each SPHEREx epoch, plus IMCCE SkyBoT known asteroids/comets at each frame time.

**Benefits.** Makes a brand-new NASA survey explorable by students and citizen scientists, teaches how astronomers identify what things are made of, and sets up a volunteer flagging loop for moving-object candidates (the way most known nearby brown dwarfs were found).

**How we built it.** Python FastAPI backend (astropy, astroquery, reproject), static web front end. Data queried live from IRSA (SIA + cutout service), cached server-side.

**Honesty rules we built in.** No discovery claims; "candidate for review" is the strongest wording. Blends are reported and fitted out (e.g. a G=16.3 star 7″ from WISE 0855: fitted jointly, its light no longer pollutes the brown dwarf's spectrum). Every molecule label cites a journal paper.

**Use of AI.** `[fill in — Space Apps asks teams to disclose AI tools; e.g. "Claude Code assisted with writing and testing backend code; all science choices were checked by the team."]`

## NASA data

- SPHEREx Spectral Images (DR1 / quick release), NASA/IPAC Infrared Science Archive (IRSA) — https://irsa.ipac.caltech.edu/Missions/spherex.html

## Space agency partner & other data

- ESA Gaia DR3 (ghost markers) — https://gea.esac.esa.int/archive/ (IRSA mirror as fallback)
- CatWISE2020, Marocco et al. 2021, ApJS 253, 8 (infrared ghost markers) — via IRSA TAP
- AllWISE, Cutri et al. 2013 (W2 flux cross-check) — via IRSA TAP
- SPHEREx ePSF calibration files (PSF photometry) — IRSA. These are from the QR3 release, and we also apply them to DR1 frames (the PSF comes from the optics, so it doesn't change between processing versions)
- IMCCE SkyBoT (known solar-system objects) — https://ssp.imcce.fr/webservices/skybot/
- SIMBAD (target coordinates) — CDS Strasbourg

## References

See `data/features.json` → `refs` (Cushing 2005, Burgasser 2006, Kirkpatrick 2005, Skemer 2016, Ootsubo 2012, DeMeo 2009, Takir & Emery 2012, …). **Verify each on ADS before submitting.**
