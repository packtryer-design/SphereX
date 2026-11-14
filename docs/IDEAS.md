# Blink: Competitor Review and Product Ideas

Status: a proposal for the team to decide on, 14 Nov 2026. Related: [PLAN.md](PLAN.md) and [BACKEND_IMAGING.md](BACKEND_IMAGING.md).

---

## 1. Why this document

Most of what Blink planned has already been built by other teams in this year's Planet X and SPHEREx challenge, often more thoroughly: the flipbook, epoch stacks, RGB and difference views, click-for-spectrum, catalog cross-checks and URL links. We need an angle nobody else has.

This document has two parts:
- **Competitor review (§2):** what other teams have built and what we can learn from them.
- **New ideas (§3–§5):** ideas that start from a real user with a real problem, not from "show the sky".

---

## 2. Competitor review

Based on reading the READMEs on 14 Nov. The live sites and the code were not checked.

| Project | What it is | Maturity | Threat |
|---|---|---|---|
| [ParallaX](https://github.com/abed-r-j/parallax-spherex) (Beirut) | Our idea, finished. Precomputed fields for all 5 targets plus Pluto and an asteroid, stacks per detector and per pass, add/subtract modes, flags overlay, URL links and embedding. Fixes the wavelength problem by predicting what an unchanging sky looks like at each frame's wavelength and subtracting that. Has a paper and slides. | Very high | **Highest** |
| [Cosmic Lens](https://github.com/MSH2006/Cosmic-Lens) | Pairs frames with matching wavelengths before subtracting (Δλ/λ < 5%), labels sources as mover / variable / not detected, cross-checks 5 catalogs, three depths of explanation (story, evidence, expert), loads your own FITS files | High | **High** |
| [Driftnet](https://github.com/epsretriever/spherex-planet-x) | A discovery engine for moving objects: survey along the ecliptic, orbit fitting, composition, AI search, measured detection limits, draft reports in the Minor Planet Center's format | Very high | High (asteroid-focused) |
| [BlinkSky](https://github.com/skibidimama106-lang/BlinkSky) (Dhaka) | A game: tap the dot that moved, collect cards, with facts from JPL | High | Medium (a different angle) |
| [nosleepclub](https://github.com/dakiemdarktharr/nosleepclub_nasa_spherex) | Deep astrometry research on WISE 0855 with heavy validation. README mostly in Vietnamese. | High in depth, low as a product | Low |
| [SPHEREx Sky Explorer](https://github.com/ashuwuin/NASA-spherex-sky-explorer) | Learning platform. The main images are WISE, not SPHEREx, and the spectra are simulated. | Medium | Low |
| [Ecluna](https://github.com/alfar1zi/ecluna) | Blinking, plus "what is the faintest mover we could have caught here, and why" | Small | Low |
| [flag-checker](https://github.com/themilan1337/spherex-flag-checker) | Command-line tool that sorts spectrum points by flag quality | Small and solid | None (a reference) |
| [spherex-photometry](https://github.com/Yancovert/spherex-photometry) | Measures brightness in source apertures, with a retro Windows-style interface | Small | None |
| [SpectraX](https://github.com/frankgyebi/SpectraX-explorer) | Empty placeholder | None | None |

These teams are at other local events, so they matter mainly if we aim for global nomination.

### Lessons we take from them

1. **Drop WISE 0855 as the hero of the demo.** Cosmic Lens reports it as **not detected**. ParallaX only gets a weak signal in detectors 5 and 6.
2. **Match wavelengths before subtracting.** Subtracting frames taken at different wavelengths makes ordinary stars look like changes. Our per-detector difference mostly cancels this out. The cheap full fix is Cosmic Lens's rule: only subtract pairs whose wavelengths are within 5%. `wavelength_um` is already stored for every frame.
3. **Pluto is the perfect demo.** It's "the original Planet X" and fits the Tombaugh hook in our pitch. ParallaX shows it drifting 12 px in 6.4 days. Within one sweep SPHEREx revisits a spot after 3–24 hours (BlinkSky measured this), so our `single` mode can already show it.
4. **Our Barnard's Star measurement holds up.** About 9.2″/yr, between Cosmic Lens (8.97″/yr) and ParallaX (10.2″/yr). Both blame the saturated core for limiting precision.
5. **Spectra (for C):** Ecluna reads the 102-channel spectrum from the **DR1 all-sky cube**, which is one tile per position with the zodiacal glow already removed. It's faster than our 358 cutouts but has no time axis. **Mask DICHROIC (bit 7)** for spectra, as flag-checker does.
6. **Reuse ideas, not code,** unless the license allows. nosleepclub and flag-checker are MIT; the others weren't checked.

---

## 3. Ideas, by real user

### Idea 1: SPHEREx Watch (alerts when SPHEREx looks at your target again)

| | |
|---|---|
| **User** | Anyone tracking one object: variable-star observers, comet watchers, brown-dwarf hunters, students following "their" star |
| **Problem** | New SPHEREx data lands every week. The only way to find out whether your target was observed is to search the archive again by hand. |
| **Idea** | Enter a target and get an **RSS feed**. Each new observation becomes an entry with dates, detectors, a new flipbook frame and an automatic "what changed since last time" difference. RSS works in any feed reader and plugs into Slack or Discord, with no accounts and no email service. |
| **Competitors** | None |
| **Fit** | Very good. The challenge says *"New SPHEREx data is arriving fast!"*, and our search is already cached daily. About 3 h of backend work. |

### Idea 2: Batch "second opinion" for citizen-science candidates

| | |
|---|---|
| **User** | Backyard Worlds volunteers, who have thousands of brown-dwarf candidates from WISE data |
| **Problem** | Each candidate needs checking by hand, and SPHEREx's newer dates and 102 colors aren't available in any tool they use |
| **Idea** | Paste a list of coordinates and get a table: Is SPHEREx coverage there? Did it move, and is that consistent with the claimed motion? Is its color brown-dwarf-like (bright at 4–5 µm, faint at 1 µm)? |
| **Competitors** | None in batch form |
| **Fit** | Medium to hard. About 358 cutouts per target from a slow IRSA, so only a small pre-computed demo list is realistic. |

### Idea 3: Classroom lab (measure a star's speed with 2026 data)

| | |
|---|---|
| **User** | Teachers and students. The Sharjah Space and Astronomy Hub runs education programs. |
| **Problem** | The standard "blink" lab exercises still use photographic plates from the 1950s |
| **Idea** | Students click Barnard's Star in epoch 1 and epoch 3. The app gives the pixel shift, students convert it to arcseconds and then km/s using its distance, and the page checks the answer. Comes with a printable worksheet. |
| **Competitors** | Partial: Cosmic Lens and Sky Explorer have short guided "missions", but none where students take a real measurement |
| **Fit** | Good. Reuses our epoch images, and `scripts/check_motion.py` already produces the answer key. About 4 h, mostly C and B. |

### Idea 4: Arabic-first

| | |
|---|---|
| **User** | Arabic-speaking students and the public, starting at our own event |
| **Problem** | There are almost no astronomy data tools in Arabic, even though many star names are Arabic in origin |
| **Idea** | A full Arabic interface with right-to-left layout and plain-language explanations, plus a short note on the Arabic origin of star names |
| **Competitors** | None |
| **Fit** | Good, but needs a native speaker to review the text. Strong local impact with Sharjah judges. |

### Idea 5: Hear the sky (accessibility)

| | |
|---|---|
| **User** | Blind and low-vision people. NASA already runs sonification projects. |
| **Problem** | Every SPHEREx tool is purely visual |
| **Idea** | A moving star becomes a tone that pans across stereo, and the spectrum plays as a chord. A screen reader announces measured facts, for example "the bright source moved 9 arcseconds north in 1 year". |
| **Competitors** | None |
| **Fit** | Good. About 3 h of frontend work in the browser's Web Audio. |

### Idea 6: "Is this point trustworthy?" for professionals (skip)

Showing quality flags and contamination for each data point is already done well by flag-checker and Cosmic Lens.

---

## 4. Comparison

| Idea | Real user with a real problem | Nobody else has it | Fits in ~20 h | Demo appeal |
|---|---|---|---|---|
| **1. SPHEREx Watch** | ✅✅ | ✅✅ | ✅✅ | ✅ |
| 2. Batch second opinion | ✅✅ | ✅ | ⚠️ | ✅ |
| 3. Classroom lab | ✅✅ | ✅ | ✅ | ✅✅ |
| 4. Arabic-first | ✅ | ✅✅ | ✅ | ✅✅ (locally) |
| 5. Hear the sky | ✅ | ✅✅ | ✅ | ✅✅ |

---

## 5. Recommendation

Keep the flipbook as the base: the challenge requires it, and it already works. Then add **one engine and one audience** on top:

- **Engine: SPHEREx Watch (Idea 1).** It's the only idea that turns "data arrives weekly" from a problem into the product, and nobody else has it.
  > *"SPHEREx never stops looking. Blink tells you the moment it looks at your star again, and shows you what changed."*
- **Audience: the classroom lab in Arabic and English (Ideas 3 + 4).** It gives the demo a human story (a student measures a star's speed live on stage) and plays well with Sharjah judges.

**If we only make one change, it's SPHEREx Watch:** the cheapest to build, and nobody else has it.

### What it changes for each person

| Person | New work | Dropped |
|---|---|---|
| **A** (imaging backend) | RSS feed endpoint and the automatic "since last visit" difference (~3 h). Wavelength-matched difference (Lesson 2). Pluto field for the demo (Lesson 3). | — |
| **B** (frontend) | Watch page, lab page, right-to-left layout | Gaia ghost markers in the viewer |
| **C** (science backend) | Lab worksheet and answer key, Arabic copy. Spectra from the DR1 cube (Lesson 5). | Gaia ghosts, SkyBoT asteroid labels |

### Updated demo path

1. **Pluto:** "Tombaugh found Planet X by blinking two plates. Here it is, drifting through SPHEREx's images."
2. **Barnard's Star:** the RGB trail, then a student-style measurement of its speed (the lab).
3. **SPHEREx Watch:** subscribe to a target live, and show the feed entry for its latest observation.

---

## 6. Open questions (ask a mentor early)

- Do the local judges value education and Arabic reach as much as we expect?
- Is a feed-based alert product clearly within "a web tool to display SPHEREx images"? We think yes, since the challenge asks for a tool that is easy to update with new data releases.
- The hour estimates are guesses, so re-check them at the 19:00 sync.
