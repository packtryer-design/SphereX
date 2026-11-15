# SpotX: 3-minute pitch

Speaker script for the 7-slide deck (`SpotX Pitch Deck.pdf`), with one live demo inside slide 3.
Speakers are a suggestion: swap names freely. Rule: **no discovery claims.** The strongest
wording is "candidate for review".

**Before you start:** open the live site in a second tab, on Barnard's Star in **Difference**
view (the home page's first featured card). Have `track.html?body=neptune` open in a third tab.

---

## Slide 1: Title (0:00–0:10) · Amro

> We're Team Ballers, and this is **SpotX**: it lets anyone watch the sky change, using NASA's
> newest space telescope.

## Slide 2: The problem (0:10–0:35) · Amro

> SPHEREx maps the whole sky every six months, in 102 colours of infrared light: more than
> 550 million stars and galaxies. It's all public. But it arrives as hundreds of raw files per
> patch of sky, one colour each, that only astronomers can open.
>
> That matters, because ordinary people make real discoveries. In 2017 a science teacher in
> Tasmania found a brown dwarf just by flipping between NASA images on Backyard Worlds. Today,
> nobody like him can look at SPHEREx at all.

## Slide 3: Our solution + live demo (0:35–1:40) · Mountacire

> SpotX is a flipbook for SPHEREx. You pick an object, and it lines up every visit SPHEREx made,
> so anything that moves jumps out. In any browser, no install.

**Switch to the site.** (≈ 55 s total)

1. **Barnard's Star, Difference view** (later visit minus earlier).
   > This is the fastest-moving star in our sky. Grey means nothing changed. This black-and-white
   > pair is the star: dark where it was, bright where it went, between two SPHEREx visits.
2. **Switch to Sequence, then click "Known objects"** (the button only works in Sequence and Blink).
   > Every ring is where the Gaia catalogue says a known star should be *on that date*. A dot
   > with no ring is worth a second look: a candidate for review, never a discovery claim.
3. **Spectrum tab** (or open WISE 0855 → Spectrum).
   > Each SPHEREx image sees one colour, so stacking them gives the light's barcode. SpotX says
   > in plain words what that object is, and only labels what the data clearly shows.

**Back to the slides.**

## Slide 4: Built on NASA open data (1:40–2:00) · Husain

> Everything is NASA and ESA open data: SPHEREx images from NASA's IRSA archive, planet orbits
> from NASA JPL Horizons, known stars from Gaia and WISE.
>
> And we check ourselves. When we track Uranus, it lands **0.3 pixels** from where JPL's orbit
> predicts, using images that never saw that prediction.

## Slide 5: Planet X search (2:00–2:30) · Husain

> The challenge asks about Planet X. A planet far beyond Pluto is too faint to see in any single
> image. So we do what astronomers do: shift every image along a guessed path and add them up.
> Only something moving that way builds up.
>
> We tested it honestly. With no hint, it found Pluto on its own. Then we planted a simulated
> planet into real SPHEREx images, fainter and fainter, and it still found one **45 times
> fainter than Pluto**. That test planet is simulated: we're measuring the method, not claiming a
> find.

## Slide 6: Impact (2:30–2:45) · Mountacire

> 2.7 million people already volunteer on Zooniverse; Backyard Worlds alone has 125,000 planet
> hunters. SpotX needs zero installs and zero logins, so any of them, or any classroom, can
> start in seconds, on any object: a star's motion, or what a world's air is made of.

## Slide 7: Next steps + thank you (2:45–3:00) · Amro

> Next, we scan the whole sky automatically for movers nobody has explained. Volunteers flag
> them, experts confirm.
>
> We haven't found Planet X. We built the tool people will use to look. Thank you.

---

## If something breaks

- **Site slow or blank:** stay on the slides and say "here's what it looks like". Slide 5's
  images are real SPHEREx frames. The backup video is `docs/media/blink-demo.mp4`.
- **Out of time:** cut the Spectrum step in slide 3 first, then shorten slide 6.

## Q&A crib

| Question | Answer |
|---|---|
| Did you find anything new? | No, and we say so on every screen. The strongest label is "candidate for review". |
| How do you know the moving dot is the planet? | JPL predicts its position independently; in every frame the dot sits within a pixel of it (Uranus 0.3 px, Neptune 0.8 px), and the spot goes dark once the planet has moved on. A background star would stay. |
| How faint can the planet search go? | We planted test planets into 46 real frames over 3 days. Recovered down to 45× fainter than Pluto; at 63× it was lost in the noise. 29% of that crowded field is hidden behind bright stars. |
| Why not just find Planet X then? | A planet hundreds of AU out moves only a few arcseconds a day, under one 6″ pixel over our 3-day window. A longer baseline across SPHEREx's six-month passes is the next step. |
| How do you know what an object is made of? | A band counts as "seen" only at 3σ against the continuum either side, and every label cites its paper. Otherwise the app says it can't tell. |
| Is the spectrum calibrated? | PSF fits with SPHEREx's official PSF models on IRSA's calibrated images, with a 3% error floor, cross-checked against WISE at 4.6 µm. |
| What about blends? | Nearby Gaia stars are fitted at the same time. WISE 0855 has a star 7″ away, and it's fitted out, not mixed in. |
| Where does the data come from? | SPHEREx via NASA/IPAC IRSA, JPL Horizons, Gaia DR3 (ESA, IRSA or VizieR mirror), CatWISE/AllWISE, IMCCE SkyBoT for known asteroids. |
| Can it run for everyone? | The demo is a static site on Netlify with results prepared in advance. The full version runs the Python API and reads live from IRSA, so new SPHEREx data shows up as it's released. |
