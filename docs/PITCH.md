# Blink102 — 3-minute pitch script

Speaker notes for the judges' demo. Times are targets; rehearse with a stopwatch.
Rule: **no discovery claims.** The strongest wording we use is "candidate for review".

---

## 1. Hook (0:00–0:20)

> In 1930, Clyde Tombaugh found Pluto by *blinking*: flipping between two photos of the same patch of sky, days apart, and looking for the one dot that moved.
> NASA's SPHEREx telescope now photographs the **whole sky** every six months, in **102 colours** of infrared. We built a blink comparator for it.

## 2. Problem (0:20–0:40)

> SPHEREx data is public, but it arrives as hundreds of thousands of raw images per field — one wavelength per image, in files only astronomers can open.
> Volunteers found most of the known nearby brown dwarfs and many comets by eye. Today they can't easily look at SPHEREx at all.

## 3. Demo (0:40–2:10)

*Open the live site. Click the guided-tour buttons in this order.*

1. **Barnard's Star — blink (≈20 s).** Press play.
   > Closest single star in the northern sky. Watch it jump — ten arcseconds a year. Each frame is a different SPHEREx visit.
2. **Rainbow trail — RGB mode (≈15 s).** Switch mode to *rgb*.
   > Three visits in red, green and blue in one picture. Still stars turn white. Anything moving leaves a rainbow trail.
3. **Gaia ghost (≈15 s).** Toggle ghosts on.
   > This circle is where the Gaia satellite predicts the star should be on that date. Star sits on its ghost: known object. A moving dot with **no** ghost and no known asteroid there is what we'd flag — a candidate for a human to review.
4. **WISE 0855 — spectrum (≈40 s).** Open WISE 0855, click it.
   > Coldest brown dwarf known — about as cold as the North Pole. Because every SPHEREx image sees it at a different wavelength, stacking them gives its full spectrum.
   > A normal star is brightest at short wavelengths. This thing is the opposite: no light at all below 4 µm, then it lights up — **at 4.0–4.45 µm it is at least 68 times brighter than a star's curve allows, at 25 sigma.** That's because **water and methane** in its air swallow the shorter wavelengths, and its heat only escapes through a clear window at 4–5 µm.
   > The app only marks a band "seen" at 3 sigma, cites the paper for every label, and here it even warns us that a faint star 7 arcseconds away is mixed into the short-wavelength light. Honest science, not pretty pictures.

*(If live data is slow: switch to the backup video at this exact point — same path.)*

## 4. Why it matters (2:10–2:40)

> Anyone with a browser can use it: no install, no account, links you can share and embed.
> It reads straight from NASA's IRSA archive, so it updates when SPHEREx releases new data every week.
> It teaches *how* astronomers know what things are made of, not just pretty pictures.

## 5. Next steps (2:40–3:00)

> Next: scan the whole sky automatically for movers with no Gaia ghost and no known asteroid, and send them to volunteers with a "Flag it" button, so the best candidates reach professionals.
> We don't claim to have found Planet X. We built the tool people will use to look.

---

## Q&A crib

| Question | Answer |
|---|---|
| Is the spectrum calibrated? | Fluxes are PSF fits with SPHEREx's official ePSFs on IRSA's calibrated, zodi-subtracted images (MJy/sr → mJy); aperture photometry only where a fit fails. A 3 % systematic floor is added to every error bar. Good for shape; absolute level ~10 %. Each spectrum is cross-checked against AllWISE W2 (4.6 µm): WISE 0855 agrees within 14 %. |
| How do you know it's water? | Band depth vs a power-law continuum fitted either side, ≥ 3σ. Band edges from Cushing 2005, Burgasser 2006 (cited in-app). For WISE 0855, SPHEREx sees the *effect* (light only escaping at 4–5 µm) rather than individual dips — it is ~25th mag below 2 µm. |
| Isn't WISE 0855 blended? | Yes — a G=16.3 star sits 7″ away, 1 pixel. We fit both stars together with the SPHEREx PSF, so the neighbour's light is split off (254 of 258 points). Before that, the "brown dwarf" showed 0.9 mJy below 2 µm — all of it the neighbour. After: zero below 4 µm, ~0.5 mJy at 4.4–5 µm, consistent with WISE W2. |
| How do you check asteroids? | IMCCE SkyBoT at each frame time; next step is cross-checking with JPL SBIdent. |
| What about Planet X itself? | Too faint/slow for a 6″ pixel in one year; the same blink + ghost logic is how a wide survey would find it. |
| Data source? | SPHEREx DR1 / quick release spectral images, IRSA SIA + cutout service; Gaia DR3 + CatWISE2020 for ghosts (CatWISE sees cold brown dwarfs Gaia can't); AllWISE W2 as flux sanity check. |
