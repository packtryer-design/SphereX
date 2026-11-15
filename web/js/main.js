import { getCatalog, getFeatures, getVisits, getFrames, getSpectrum, getPointSpectrum, resolveName, getGhosts, getAsteroids, OfflineError, NotInDemoError, snapshotIds } from "./api.js";
import { readState, writeState, TABS } from "./state.js";
import { Pane, skyAt, fracAt, formatRaDec } from "./viewer.js";
import { sampleLayers } from "./sample.js";
import { drawSpectrum, drawSeries } from "./spectrum.js";
import { setupSearch, visitBadge } from "./search.js";
import { KINDS, SIMBAD_TYPES, kindFromType, detectorText, wavelengthText } from "./kinds.js";
import { formatDate, formatMonth, formatRange, formatGap } from "./time.js";

const $ = (id) => document.getElementById(id);
const ui = {
  home: $("home"), homeLink: $("home-link"), catalog: $("catalog"), object: $("object"),
  objName: $("obj-name"), objSub: $("obj-sub"),
  tabs: [...document.querySelectorAll("[role=tab]")],
  viewer: $("viewer"), swipe: $("swipe-handle"), marker: $("marker"),
  stamp: $("stamp"), stampDate: $("stamp-date"), stampSub: $("stamp-sub"),
  caveat: $("caveat"), legend: $("legend"), msg: $("msg"),
  knownToggle: $("known-toggle"), knownLayer: $("known-layer"), knownNote: $("known-note"),
  spot: $("spot"), spotClose: $("spot-close"), spotPos: $("spot-pos"), spotChart: $("spot-chart"), spotSpectrum: $("spot-spectrum"),
  viewButtons: [...document.querySelectorAll(".views [data-view]")], // not #viewer, which has data-view too
  play: $("play"), pair: $("pair"), pickA: $("pick-a"), pickB: $("pick-b"), track: $("track"),
  obsTitle: $("obs-title"), obsSummary: $("obs-summary"), obsList: $("obs-list"),
  specPos: $("spec-pos"), specCentre: $("spec-centre"), specChart: $("spec-chart"), specLegend: $("spec-legend"), specMsg: $("spec-msg"), specSci: $("spec-sci"),
  specLede: $("spec-lede"), specNotes: $("spec-notes"), specLoading: $("spec-loading"),
  bandsTitle: $("bands-title"), bandsNote: $("bands-note"), bandsList: $("bands-list"),
  aboutName: $("about-name"), aboutKind: $("about-kind"), aboutText: $("about-text"), aboutTime: $("about-time"),
  aboutFacts: $("about-facts"), aboutLinks: $("about-links"),
};
const paneA = new Pane($("pane-a"));
const paneB = new Pane($("pane-b"));

const SEQUENCE_MS = 1800, SEQUENCE_FADE = 700;
const BLINK_MS = 650, BLINK_FADE = 90;
const STEP_FADE = 450;

let catalog = [];
let demoMode = false; // true when reading the static snapshot instead of a live API
let features = { bands: [], glossary: {} };
let obj = null;          // the open object
let visits = [];         // [{epoch, mjd_start, mjd_end, n_frames, detectors, full_coverage, frame, color}]
let imagesReady = false;
let status = "loading"; // loading | none | ok | error: what the visit list said
const state = { tab: "explore", view: "sequence", cur: 0, a: 0, b: 0 };
let ctrl = null;         // aborts requests for the previous object
let token = 0;
const frameCache = new Map();
let timer = null;
let blinkShowsB = false;
let spot = null;         // {ra, dec, x, y} last clicked spot
let spectrumKey = null;
let spectrumData = null;
const hiddenVisits = new Set();
let known = null;        // {stars, asteroids, failed} for the open object, once fetched
let knownLoading = false;
let showKnown = false;

// ---------- small helpers ----------

const isCompare = (v = state.view) => ["blink", "side", "swipe", "diff"].includes(v);
const sameDets = (x, y) => (x?.detectors ?? []).join() === (y?.detectors ?? []).join();
const visitName = (i) => `Visit ${i + 1}`;
const visitColor = (i, n) => `hsl(${n > 1 ? 205 - (180 * i) / (n - 1) : 205} 85% 66%)`;
const withImage = () => visits.map((v, i) => (v.frame ? i : -1)).filter((i) => i >= 0);

function nearestWithImage(i) {
  const ids = withImage();
  if (!ids.length) return 0;
  return ids.reduce((best, j) => (Math.abs(j - i) < Math.abs(best - i) ? j : best), ids[0]);
}

function indexOfEpoch(epoch) {
  const i = visits.findIndex((v) => v.epoch === epoch);
  return i >= 0 ? i : null;
}

function visitOfMjd(mjd) {
  const i = visits.findIndex((v) => mjd >= v.mjd_start - 0.5 && mjd <= v.mjd_end + 0.5);
  return i >= 0 ? i : null;
}

function showMsg(kind, title = "", text = "") {
  if (!kind) {
    ui.msg.hidden = true;
    return;
  }
  const box = document.createElement("div");
  if (kind === "loading") box.append(Object.assign(document.createElement("div"), { className: "spinner" }));
  const b = document.createElement("b");
  b.textContent = title;
  const p = document.createElement("p");
  p.textContent = text;
  box.append(b, p);
  ui.msg.replaceChildren(box);
  ui.msg.hidden = false;
}

function errorText(err) {
  if (err instanceof NotInDemoError) return ["Not in this demo", err.message];
  if (err instanceof OfflineError) {
    return [err.message, "Images and spectra come from SpotX's Python server or its demo snapshot, and neither is available. To run it yourself: `make serve`, then open http://localhost:8000."];
  }
  if (err.status === 503) return ["NASA's archive is busy", `${err.message}. Try again in a minute.`];
  return ["Something went wrong", err.message];
}

function frames(mode, ref) {
  const key = `${mode}:${ref ?? ""}`;
  if (!frameCache.has(key)) {
    const p = getFrames({ ra: obj.ra, dec: obj.dec, fov: obj.fov, mode, ref }, ctrl.signal);
    p.catch(() => frameCache.delete(key));
    frameCache.set(key, p);
  }
  return frameCache.get(key);
}

function syncUrl() {
  writeState({
    object: obj,
    tab: state.tab,
    view: state.view,
    visit: visits[state.cur]?.epoch,
    a: visits[state.a]?.epoch,
    b: visits[state.b]?.epoch,
  });
}

// ---------- home: the catalog ----------

// The catalog name people know (M 42, NGC 7293), not the first SIMBAD alias (LBN 209.13-19.35).
function shortName(o) {
  const names = [o.simbad_id, ...(o.aliases ?? [])].filter((n) => n && n !== o.name);
  return names.find((n) => /^(M|NGC|IC|GJ) /.test(n)) ?? names.find((n) => !/^(LBN|Ced|NAME) /.test(n)) ?? "";
}

function renderCatalog() {
  // Things that visibly change go first; nebulae (which don't) after.
  const first = ["moving_star", "brown_dwarf", "young_star", "variable_star"];
  const order = ["stars", ...Object.keys(KINDS).filter((k) => !first.includes(k))];
  const groups = new Map(order.map((k) => [k, []]));
  for (const k of first) for (const o of catalog) if (o.kind === k) groups.get("stars").push(o);
  for (const o of catalog) if (!first.includes(o.kind)) (groups.get(o.kind) ?? groups.get("unknown")).push(o);
  ui.catalog.replaceChildren(...[...groups].filter(([, list]) => list.length).map(([kind, list]) => {
    const sec = document.createElement("section");
    const h = document.createElement("h2");
    h.textContent = kind === "stars" ? "Stars that move or change" : KINDS[kind].plural;
    const cards = document.createElement("div");
    cards.className = "cards";
    cards.append(...list.map((o) => {
      const b = document.createElement("button");
      b.className = "card";
      b.innerHTML = `<img class="c-img" alt="" loading="lazy"><span class="c-name"></span><span class="c-sub"></span><span class="badge"></span>`;
      const img = b.querySelector(".c-img");
      img.addEventListener("error", () => img.remove(), { once: true });
      img.src = `data/thumbs/${encodeURIComponent(o.id)}.jpg`;
      b.querySelector(".c-name").textContent = o.name;
      b.querySelector(".c-sub").textContent = kind === "stars"
        ? [KINDS[o.kind]?.label, o.constellation].filter(Boolean).join(" · ")
        : [shortName(o), o.constellation].filter(Boolean).join(" · ");
      const badge = visitBadge(o);
      const el = b.querySelector(".badge");
      el.textContent = badge.text;
      if (badge.cls) el.classList.add(badge.cls);
      if (!badge.text) el.remove();
      b.addEventListener("click", () => openObject(o));
      return b;
    }));
    sec.append(h, cards);
    return sec;
  }));
}

function showHome() {
  stop();
  ctrl?.abort();
  token++;
  obj = null;
  ui.object.hidden = true;
  ui.home.hidden = false;
  document.title = "SpotX";
  syncUrl();
}

// ---------- opening an object ----------

async function openObject(o, opts = {}) {
  stop();
  closeSpot();
  ctrl?.abort();
  ctrl = new AbortController();
  const my = ++token;
  obj = o;
  visits = [];
  imagesReady = false;
  status = "loading";
  frameCache.clear();
  spectrumKey = null;
  spectrumData = null;
  renderBands();
  hiddenVisits.clear();
  known = null;
  knownLoading = false;
  drawKnown();
  paneA.clear();
  paneB.clear();

  ui.home.hidden = true;
  ui.object.hidden = false;
  document.title = `${o.name} · SpotX`;
  ui.objName.textContent = o.name;
  ui.objSub.textContent = [KINDS[o.kind]?.label, o.constellation && `in ${o.constellation}`].filter(Boolean).join(" ");
  setView(opts.view ?? "sequence", { quiet: true });
  setTab(opts.tab ?? "explore", { quiet: true });
  renderAbout();
  renderTrack();
  renderObservations();
  updateStage();
  showMsg("loading", "Checking SPHEREx visits…", `Asking NASA's archive when SPHEREx looked at ${o.name}.`);

  let v;
  try {
    v = await getVisits(o, ctrl.signal);
  } catch (err) {
    if (err.name === "AbortError" || my !== token) return;
    status = "error";
    showMsg("error", ...errorText(err));
    renderObservations(err);
    return;
  }
  if (my !== token) return;

  visits = v.visits.map((x, i, all) => ({ ...x, frame: null, color: visitColor(i, all.length) }));
  status = visits.length ? "ok" : "none";
  renderAbout();
  if (!visits.length) {
    showMsg("empty", "SPHEREx hasn't observed this spot yet",
      "No SPHEREx exposures cover this position in the data releases SpotX searches. There's nothing to compare yet. New data arrives weekly, so check back later.");
    renderTrack();
    renderObservations();
    syncUrl();
    return;
  }
  const last = visits.length - 1;
  state.cur = indexOfEpoch(opts.visit) ?? 0;
  state.a = indexOfEpoch(opts.a) ?? 0;
  state.b = indexOfEpoch(opts.b) ?? last;
  renderTrack();
  renderPair();
  renderObservations();
  syncUrl();
  // A star's spectrum uses its own small cutouts, not the images: no need to wait for them.
  if (isPointSource() && state.tab === "spectrum") loadSpectrum();

  const exposures = visits.reduce((n, x) => n + x.n_frames, 0);
  showMsg("loading", `Building images of ${visits.length} visit${visits.length > 1 ? "s" : ""}`,
    `Combining ${exposures} SPHEREx exposures onto one grid. The first time downloads them from NASA and can take several minutes; after that it's instant.`);
  let ep;
  try {
    ep = await frames("epoch");
  } catch (err) {
    if (err.name === "AbortError" || my !== token) return;
    showMsg("error", ...errorText(err));
    return;
  }
  if (my !== token) return;

  for (const f of ep.frames) {
    const i = visitOfMjd(f.mjd_start ?? f.mjd) ?? visitOfMjd(f.mjd);
    if (i != null) visits[i].frame = f;
    new Image().src = f.png; // preload so stepping is instant
  }
  imagesReady = true;
  if (!withImage().length) {
    showMsg("empty", "No usable image",
      "SPHEREx covered this position, but only at the very edge of its detectors, so SpotX couldn't build a clean image from any visit.");
    renderTrack();
    renderObservations();
    return;
  }
  state.cur = nearestWithImage(state.cur);
  state.a = nearestWithImage(state.a);
  state.b = nearestWithImage(state.b);
  if (state.a === state.b && withImage().length > 1) state.b = withImage().at(-1) === state.a ? withImage()[0] : withImage().at(-1);
  showMsg(null);
  renderTrack();
  renderPair();
  renderObservations();
  refresh(0);
  if (state.view === "blink") startBlink();
  if (state.tab === "spectrum") loadSpectrum();
}

async function lookup(name) {
  const local = catalog.find((o) => o.name.toLowerCase() === name.toLowerCase());
  if (local) return openObject(local);
  ui.home.hidden = true;
  ui.object.hidden = false;
  ui.objName.textContent = name;
  ui.objSub.textContent = "";
  showMsg("loading", `Looking up “${name}”…`, "Searching SIMBAD and NED.");
  try {
    const r = await resolveName(name);
    const known = catalog.find((o) => o.simbad_id === r.catalog_name);
    if (known) return openObject(known);
    openObject({
      custom: true,
      name: r.name,
      ra: r.ra,
      dec: r.dec,
      fov: 0.2,
      kind: kindFromType(r.type),
      simbad_id: r.catalog_name,
      simbad_type: r.type,
      constellation: r.constellation,
      source: r.source,
      aliases: r.catalog_name && r.catalog_name !== r.name ? [r.catalog_name] : [],
    });
  } catch (err) {
    if (err.status === 404) showMsg("error", `Nothing called “${name}”`, "Try a catalog name such as M 42 or NGC 7293.");
    else showMsg("error", ...errorText(err));
  }
}

// ---------- tabs ----------

function setTab(tab, { quiet = false } = {}) {
  state.tab = TABS.includes(tab) ? tab : "explore";
  for (const t of ui.tabs) {
    const on = t.dataset.tab === state.tab;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
    $(`panel-${t.dataset.tab}`).hidden = !on;
  }
  if (state.tab !== "explore") stop();
  if (state.tab === "spectrum") loadSpectrum();
  if (!quiet) syncUrl();
}

// ---------- explore: views ----------

function setView(view, { quiet = false } = {}) {
  stop();
  state.view = view;
  ui.viewer.dataset.view = view;
  for (const b of ui.viewButtons) b.setAttribute("aria-checked", String(b.dataset.view === view));
  ui.swipe.hidden = view !== "swipe";
  ui.pair.hidden = !isCompare(view);
  ui.play.hidden = !(view === "sequence" || view === "blink");
  if (view !== "side" && view !== "swipe") paneB.clear();
  renderTrack();
  drawKnown(); // now, not after the new view's image loads
  if (quiet) return;
  refresh(0);
  if (view === "blink") startBlink();
  syncUrl();
}

function updateStage() {
  ui.caveat.hidden = true;
  ui.legend.hidden = true;
  ui.stamp.hidden = !imagesReady;
}

function caveat(text) {
  ui.caveat.textContent = text;
  ui.caveat.hidden = !text;
}

function pairCaveat(A, B) {
  if (!sameDets(A, B)) {
    return `These visits used different detectors (A: ${A.detectors.join(", ")} · B: ${B.detectors.join(", ")}), so they show different infrared colours. Differences may be colour, not change.`;
  }
  return "";
}

function stampFor(i) {
  const v = visits[i];
  ui.stampDate.textContent = formatRange(v.mjd_start, v.mjd_end);
  ui.stampSub.textContent = `${visitName(i)} of ${visits.length} · ${v.n_frames} exposures · ${detectorText(v.detectors)}`;
}

// Redraw the explore stage for the current view. fade: crossfade length in ms.
async function refresh(fade = STEP_FADE) {
  if (!obj || !imagesReady) return;
  showMsg(null);
  updateStage();
  const view = state.view;
  const A = visits[state.a], B = visits[state.b];

  if (view === "sequence") {
    const v = visits[state.cur];
    stampFor(state.cur);
    caveat(v.full_coverage ? "" : `Partial visit: only ${detectorText(v.detectors)} (${wavelengthText(v.detectors)}), so fewer infrared colours than a full visit.`);
    await paneA.show(v.frame.png, `${obj.name}, ${formatRange(v.mjd_start, v.mjd_end)}`, fade);
  } else if (view === "blink") {
    const i = blinkShowsB ? state.b : state.a;
    stampFor(i);
    ui.stampDate.style.color = blinkShowsB ? "var(--b)" : "var(--a)";
    caveat(pairCaveat(A, B));
    await paneA.show(visits[i].frame.png, `${obj.name}, ${blinkShowsB ? "B" : "A"}`, fade);
  } else if (view === "side" || view === "swipe") {
    ui.stampDate.textContent = `${formatGap(Math.abs(B.mjd_start - A.mjd_start))} apart`;
    ui.stampSub.textContent = `A: ${formatRange(A.mjd_start, A.mjd_end)} · B: ${formatRange(B.mjd_start, B.mjd_end)}`;
    paneA.setLabel(`A · ${formatRange(A.mjd_start, A.mjd_end)}`);
    paneB.setLabel(`B · ${formatRange(B.mjd_start, B.mjd_end)}`);
    caveat(pairCaveat(A, B));
    await Promise.all([
      paneA.show(A.frame.png, `${obj.name}, visit A`, fade),
      paneB.show(B.frame.png, `${obj.name}, visit B`, fade),
    ]);
  } else if (view === "diff") {
    await showDiff(fade);
  } else if (view === "rgb") {
    await showRgb(fade);
  }
  ui.stampDate.style.color = view === "blink" ? ui.stampDate.style.color : "";
  drawKnown();
}

// ---------- explore: known objects ("Is this new?") ----------
// Rings where Gaia DR3 / CatWISE2020 put each catalogued star on this visit's date, squares on
// known asteroids. A dot with no ring is worth a second look: a candidate, never a discovery.

function knownVisit() {
  if (state.view === "sequence") return state.cur;
  if (state.view === "blink") return blinkShowsB ? state.b : state.a;
  return null;
}

function knownNote(html) {
  ui.knownNote.innerHTML = html;
  ui.knownNote.hidden = !html;
}

function loadKnown() {
  if (known || knownLoading || !obj) return;
  knownLoading = true;
  const my = token;
  const q = { ra: obj.ra, dec: obj.dec, fov: obj.fov };
  knownNote("Looking up known stars and asteroids… The first time takes up to a minute.");
  Promise.allSettled([getGhosts(q, ctrl.signal), getAsteroids(q, ctrl.signal)]).then(([g, a]) => {
    if (my !== token) return;
    knownLoading = false;
    known = {
      stars: g.value?.stars ?? [],
      asteroids: a.value?.objects ?? [],
      failed: [g.status === "rejected" && "the star catalogues (Gaia, CatWISE)", a.status === "rejected" && "the asteroid list (SkyBoT)"].filter(Boolean),
    };
    drawKnown();
  });
}

function drawKnown() {
  const layer = ui.knownLayer;
  const i = knownVisit();
  layer.toggleAttribute("hidden", true); // an <svg> has no .hidden property
  // one visit on screen at a time, or the marks would belong to neither image
  ui.knownToggle.disabled = i == null;
  ui.knownToggle.title = i == null ? "Known objects are marked in the Sequence and Blink views" : "Mark where catalogued stars and known asteroids should be on each visit's date";
  if (!showKnown || !obj || !imagesReady || i == null) return knownNote("");
  if (!known) return loadKnown();

  const v = visits[i];
  const mjd = v.frame?.mjd ?? (v.mjd_start + v.mjd_end) / 2;
  const at = (ra, dec) => {
    const { fx, fy } = fracAt(obj, ra, dec);
    return [(fx * 100).toFixed(2), (fy * 100).toFixed(2)];
  };
  const marks = [];
  let nStars = 0;
  for (const s of known.stars) {
    const p = s.positions.find((x) => x.epoch === v.epoch);
    if (!p) continue;
    const [x, y] = at(p.ra, p.dec);
    marks.push(`<circle class="${s.catalog === "catwise" ? "catwise" : "gaia"}" cx="${x}" cy="${y}" r="2.2"/>`);
    nStars++;
  }
  const names = [];
  for (const o of known.asteroids) {
    const here = o.positions.filter((x) => x.epoch === v.epoch);
    if (!here.length) continue;
    const p = here.reduce((b, x) => (Math.abs(x.mjd - mjd) < Math.abs(b.mjd - mjd) ? x : b));
    const [x, y] = at(p.ra, p.dec);
    marks.push(`<rect class="asteroid" x="${x - 2.5}" y="${y - 2.5}" width="5" height="5"/><text x="${+x + 3.5}" y="${+y + 1}">${esc(o.name)}</text>`);
    names.push(esc(o.number ? `(${o.number}) ${o.name}` : o.name));
  }
  layer.innerHTML = marks.join("");
  layer.toggleAttribute("hidden", false);

  const rows = [
    `<span class="ring" style="color:var(--ghost-gaia)"></span>Gaia star, moved to this date · <span class="ring" style="color:var(--ghost-catwise)"></span>CatWISE (infrared only)`,
    `${nStars} catalogued star${nStars === 1 ? "" : "s"} here. ${names.length ? `Known asteroid${names.length > 1 ? "s" : ""}: ${names.join(", ")}.` : "No known asteroids at this visit."}`,
    `<span class="fine">A dot with no ring on it is worth a closer look: a candidate for review, not a discovery.</span>`,
  ];
  if (known.failed.length) rows.push(`<span class="fine" style="color:var(--warn)">Couldn't reach ${known.failed.join(" or ")} just now, so some marks are missing. Turn Known objects off and on to try again.</span>`);
  knownNote(rows.join("<br>"));
}

function toggleKnown() {
  showKnown = !showKnown;
  ui.knownToggle.setAttribute("aria-pressed", String(showKnown));
  if (showKnown && known?.failed.length) known = null; // retry what failed last time
  drawKnown();
}

async function showDiff(fade) {
  const A = visits[state.a], B = visits[state.b];
  ui.stampDate.textContent = "B minus A";
  ui.stampSub.textContent = `${formatRange(B.mjd_start, B.mjd_end)} minus ${formatRange(A.mjd_start, A.mjd_end)} · ${formatGap(Math.abs(B.mjd_start - A.mjd_start))} apart`;
  if (state.a === state.b) {
    paneA.clear();
    showMsg("empty", "Pick two different visits", "Difference shows what changed from visit A to visit B.");
    return;
  }
  const my = token;
  showMsg("loading", "Subtracting visits…", "Matching detectors between the two visits.");
  let d;
  try {
    d = await frames("diff", A.frame.epoch);
  } catch (err) {
    if (err.name !== "AbortError" && my === token) showMsg("error", ...errorText(err));
    return;
  }
  if (my !== token || state.view !== "diff") return;
  const f = d.frames.find((x) => x.epoch === B.frame.epoch);
  if (!f) {
    paneA.clear();
    showMsg("empty", "These visits share no detector",
      "They saw the field in completely different infrared colours, so subtracting them would show colour, not change. Pick another pair.");
    return;
  }
  showMsg(null);
  const shared = f.detectors ?? [];
  caveat(shared.length && !(sameDets(A, B) && A.detectors.length === shared.length)
    ? `Only the detectors both visits share were compared: ${shared.join(", ")}.`
    : "");
  ui.legend.innerHTML = `<span class="swatch" style="background:#808080"></span>Grey: no change<br>
    <span class="swatch" style="background:#fff"></span>Brighter in B
    <span class="swatch" style="background:#000;margin-left:8px"></span>Fainter in B<br>
    <span class="fine">Scale: ±5× the noise. Speckle is noise. A bright and dark pair side by side means something moved.</span>`;
  ui.legend.hidden = false;
  await paneA.show(f.png, `${obj.name}, difference between visits`, fade);
}

async function showRgb(fade) {
  ui.stampDate.textContent = "Colour-time";
  ui.stampSub.textContent = "Visits coloured red, green and blue";
  caveat("");
  if (withImage().length < 2) {
    paneA.clear();
    showMsg("empty", "Needs at least two visits", "Colour-time puts different visits in different colours.");
    return;
  }
  const my = token;
  showMsg("loading", "Combining visits into one colour image…", "");
  let r;
  try {
    r = await frames("rgb");
  } catch (err) {
    if (err.name !== "AbortError" && my === token) showMsg("error", ...errorText(err));
    return;
  }
  if (my !== token || state.view !== "rgb") return;
  const f = r.frames[0];
  if (!f) {
    showMsg("empty", "Not enough visits with images", "");
    return;
  }
  showMsg(null);
  const byEpoch = (e) => visits.find((v) => v.frame?.epoch === e);
  const chans = (f.epochs ?? []).map((e, i) => ({ e, color: ["#ff4d4d", "#4dff6a", "#4d8bff"][i] }));
  const seen = new Map();
  for (const c of chans) {
    if (!seen.has(c.e)) seen.set(c.e, []);
    seen.get(c.e).push(c.color);
  }
  const rows = [...seen].map(([e, colors]) => {
    const v = byEpoch(e);
    const sw = colors.map((c) => `<span class="swatch" style="background:${c}"></span>`).join("");
    return `${sw}${v ? formatRange(v.mjd_start, v.mjd_end) : `epoch ${e}`}`;
  });
  ui.legend.innerHTML = `${rows.join("<br>")}<br><span class="fine">White or grey: the same in every visit. Coloured: brighter in some visits than others, or moved.</span>`;
  ui.legend.hidden = false;
  if (seen.size > 1) {
    const first = byEpoch(chans[0].e), lastV = byEpoch(chans.at(-1).e);
    if (first && lastV && !sameDets(first, lastV)) caveat("These visits used different detectors, so colours can come from wavelength differences, not change.");
  }
  await paneA.show(f.png, `${obj.name}, visits as colours`, fade);
}

// ---------- timeline ----------

function renderTrack() {
  ui.track.replaceChildren();
  if (!visits.length) return;
  const mids = visits.map((v) => (v.mjd_start + v.mjd_end) / 2);
  const t0 = mids[0], t1 = mids.at(-1);
  const pos = (t) => (visits.length === 1 ? 50 : ((t - t0) / (t1 - t0)) * 100);
  ui.track.classList.toggle("dense", visits.length > 6);
  ui.track.classList.toggle("sparse", visits.length <= 4);

  if (visits.length <= 8) {
    for (let i = 1; i < visits.length; i++) {
      const g = document.createElement("span");
      g.className = "gap";
      g.style.left = `${(pos(mids[i - 1]) + pos(mids[i])) / 2}%`;
      g.textContent = formatGap(visits[i].mjd_start - visits[i - 1].mjd_end);
      ui.track.append(g);
    }
  }
  visits.forEach((v, i) => {
    const b = document.createElement("button");
    b.className = "visit";
    b.style.left = `${pos(mids[i])}%`;
    const missing = imagesReady && !v.frame;
    b.classList.toggle("missing", missing);
    b.classList.toggle("partial", !v.full_coverage);
    if (state.view === "sequence") b.classList.toggle("current", i === state.cur);
    if (isCompare()) {
      b.classList.toggle("is-a", i === state.a);
      b.classList.toggle("is-b", i === state.b && i !== state.a);
    }
    b.innerHTML = `<span class="dot"></span><span class="when"></span>`;
    b.querySelector(".when").textContent = formatMonth(v.mjd_start);
    const extra = missing ? ". No usable image" : v.full_coverage ? "" : `. Partial: ${detectorText(v.detectors)}`;
    b.title = `${visitName(i)}: ${formatRange(v.mjd_start, v.mjd_end)}${extra}`;
    b.setAttribute("aria-label", b.title);
    b.addEventListener("click", () => pickVisit(i));
    ui.track.append(b);
  });
}

function pickVisit(i) {
  if (!imagesReady || !visits[i]?.frame) return;
  if (state.view === "sequence") {
    stop();
    state.cur = i;
  } else if (isCompare()) {
    if (i === state.a) return;
    state.b = i;
    renderPair();
  } else {
    return;
  }
  renderTrack();
  refresh();
  syncUrl();
}

function renderPair() {
  for (const [sel, key] of [[ui.pickA, "a"], [ui.pickB, "b"]]) {
    sel.replaceChildren(...visits.map((v, i) => {
      const o = document.createElement("option");
      o.value = i;
      o.textContent = formatRange(v.mjd_start, v.mjd_end);
      o.disabled = imagesReady && !v.frame;
      return o;
    }));
    sel.value = state[key];
  }
}

function onPairChange(key, value) {
  state[key] = Number(value);
  renderTrack();
  refresh();
  syncUrl();
}

// ---------- play / blink ----------

function stop() {
  clearInterval(timer);
  timer = null;
  blinkShowsB = false;
  ui.play.textContent = "▶";
  ui.play.setAttribute("aria-label", state.view === "blink" ? "Start blinking" : "Play");
}

function step(dir) {
  const ids = withImage();
  if (!ids.length) return;
  const k = ids.indexOf(state.cur);
  state.cur = ids[(k + dir + ids.length) % ids.length];
}

function togglePlay() {
  if (!imagesReady) return;
  if (timer) return stop();
  if (state.view === "blink") return startBlink();
  timer = setInterval(() => {
    step(1);
    renderTrack();
    refresh(SEQUENCE_FADE);
    syncUrl();
  }, SEQUENCE_MS);
  ui.play.textContent = "❚❚";
  ui.play.setAttribute("aria-label", "Pause");
}

function startBlink() {
  if (!imagesReady || state.view !== "blink") return;
  stop();
  timer = setInterval(() => {
    blinkShowsB = !blinkShowsB;
    refresh(BLINK_FADE);
  }, BLINK_MS);
  ui.play.textContent = "❚❚";
  ui.play.setAttribute("aria-label", "Stop blinking");
}

// ---------- swipe ----------

function setSplit(pct) {
  const p = Math.min(100, Math.max(0, pct));
  ui.viewer.style.setProperty("--split", `${p}%`);
  ui.swipe.setAttribute("aria-valuenow", String(Math.round(p)));
}

function setupSwipe() {
  let dragging = false;
  const move = (e) => {
    if (!dragging) return;
    const r = ui.viewer.getBoundingClientRect();
    setSplit(((e.clientX - r.left) / r.width) * 100);
  };
  ui.swipe.addEventListener("pointerdown", (e) => {
    dragging = true;
    ui.swipe.setPointerCapture(e.pointerId);
  });
  ui.swipe.addEventListener("pointermove", move);
  ui.swipe.addEventListener("pointerup", () => { dragging = false; });
  ui.swipe.addEventListener("keydown", (e) => {
    const now = Number(ui.swipe.getAttribute("aria-valuenow"));
    if (e.key === "ArrowLeft") { e.preventDefault(); e.stopPropagation(); setSplit(now - 5); }
    if (e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); setSplit(now + 5); }
  });
}

// ---------- click a spot: brightness over time ----------

async function onPaneClick(e, pane) {
  if (!imagesReady) return;
  const r = pane.imageRect();
  if (!r) return;
  const fx = (e.clientX - r.left) / r.width;
  const fy = (e.clientY - r.top) / r.height;
  if (fx < 0 || fx > 1 || fy < 0 || fy > 1) return;
  const box = ui.viewer.getBoundingClientRect();
  ui.marker.style.left = `${e.clientX - box.left}px`;
  ui.marker.style.top = `${e.clientY - box.top}px`;
  ui.marker.hidden = false;
  spot = { ...skyAt(obj, fx, fy), fx, fy };
  ui.spot.hidden = false;
  ui.spotPos.textContent = formatRaDec(spot.ra, spot.dec);
  ui.spotChart.textContent = "Reading…";

  const shown = visits.filter((v) => v.frame);
  try {
    const pts = await sampleLayers(shown.map((v) => ({ png: v.frame.png, wavelength_um: 0 })), fx, fy);
    drawSeries(ui.spotChart, pts.map((p, i) => ({
      mjd: shown[i].frame.mjd, flux: p.flux * 100, err: p.err * 100, color: shown[i].color, label: formatMonth(shown[i].mjd_start),
    })), { yLabel: "display brightness (%)" });
  } catch (err) {
    ui.spotChart.textContent = `Couldn't read the images: ${err.message}`;
  }
}

function closeSpot() {
  ui.spot.hidden = true;
  ui.marker.hidden = true;
}

// ---------- observations tab ----------

function renderObservations(err) {
  ui.obsTitle.textContent = obj ? `Observations of ${obj.name}` : "Observations";
  if (err) {
    ui.obsSummary.textContent = errorText(err).join(". ");
    ui.obsList.replaceChildren();
    return;
  }
  if (!visits.length) {
    ui.obsSummary.textContent = status === "none" ? "SPHEREx hasn't observed this position yet." : "Checking SPHEREx's archive…";
    ui.obsList.replaceChildren();
    return;
  }
  const first = visits[0], last = visits.at(-1);
  const gaps = visits.slice(1).map((v, i) => v.mjd_start - visits[i].mjd_end);
  const typical = gaps.length ? formatGap(gaps.sort((x, y) => x - y)[Math.floor(gaps.length / 2)]) : null;
  const partial = visits.filter((v) => !v.full_coverage).length;
  ui.obsSummary.textContent = [
    `${visits.length} visit${visits.length > 1 ? "s" : ""} between ${formatDate(first.mjd_start)} and ${formatDate(last.mjd_end)}.`,
    typical && `Typical gap between visits: ${typical}.`,
    partial && `${partial} visit${partial > 1 ? "s" : ""} used only some detectors.`,
    "SPHEREx maps the whole sky about every six months, so most places get roughly two visits a year. Near the ecliptic poles it passes far more often.",
  ].filter(Boolean).join(" ");

  ui.obsList.replaceChildren(...visits.map((v, i) => {
    const card = document.createElement("article");
    card.className = "obs";
    const img = document.createElement("div");
    img.className = "obs-img";
    if (v.frame) {
      const im = document.createElement("img");
      im.src = v.frame.png;
      im.alt = `${obj.name}, ${formatRange(v.mjd_start, v.mjd_end)}`;
      im.loading = "lazy";
      img.append(im);
    } else {
      img.textContent = imagesReady ? "No usable image (object at a detector edge)" : "Image building…";
    }
    const body = document.createElement("div");
    body.className = "obs-body";
    const date = Object.assign(document.createElement("div"), { className: "o-date", textContent: formatRange(v.mjd_start, v.mjd_end) });
    const days = Math.round(v.mjd_end - v.mjd_start) + 1;
    const after = i ? ` · ${formatGap(v.mjd_start - visits[i - 1].mjd_end)} after the previous visit` : "";
    const meta = Object.assign(document.createElement("div"), {
      className: "o-meta",
      textContent: `${visitName(i)} · ${v.n_frames} exposures over ${days} day${days > 1 ? "s" : ""}${after}`,
    });
    const dets = document.createElement("div");
    dets.className = "dets";
    dets.title = `Detectors: ${wavelengthText(v.detectors)}`;
    for (let d = 1; d <= 6; d++) {
      const s = Object.assign(document.createElement("span"), { className: `det${v.detectors.includes(d) ? " on" : ""}`, textContent: d });
      dets.append(s);
    }
    const actions = document.createElement("div");
    actions.className = "obs-actions";
    const btn = (label, fn) => {
      const b = Object.assign(document.createElement("button"), { textContent: label });
      b.disabled = !v.frame;
      b.addEventListener("click", fn);
      return b;
    };
    actions.append(
      btn("View", () => { state.cur = i; setTab("explore"); setView("sequence"); }),
      btn("Set as A", () => { state.a = i; if (state.b === i) state.b = nearestWithImage(i + 1); renderPair(); if (!isCompare()) setView("blink"); setTab("explore"); renderTrack(); refresh(); syncUrl(); }),
      btn("Set as B", () => { state.b = i; if (state.a === i) state.a = nearestWithImage(i - 1); renderPair(); if (!isCompare()) setView("blink"); setTab("explore"); renderTrack(); refresh(); syncUrl(); }),
    );
    body.append(date, meta, dets, actions);
    card.append(img, body);
    return card;
  }));
}

// ---------- spectrum tab ----------
// Two methods, picked by what the object is:
//   point sources (stars, brown dwarfs): /api/spectrum, Person C's PSF photometry in mJy,
//     with molecule bands, saturation note, WISE W2 cross-check and nearby-star blends
//   extended objects (nebulae): /api/surface-spectrum, surface brightness in MJy/sr
// (aperture photometry with a sky ring would subtract a nebula's own light).

const POINT_KINDS = new Set(["moving_star", "brown_dwarf", "young_star", "variable_star"]);
const isPointSource = () => Boolean(obj && (obj.spectrum === "point" || obj.target_id || POINT_KINDS.has(obj.kind)));

const BAND_STATUS = {
  seen: "Seen",
  not_clear: "Not clear",
  opposite: "Opposite of expected",
  too_faint: "Too faint here",
  no_coverage: "No data at these wavelengths",
};

function renderBands(s) {
  if (isPointSource()) {
    const fb = s?.features?.bands ?? [];
    ui.bandsTitle.textContent = "What to look for";
    ui.bandsNote.textContent = fb.length
      ? "Where substances in this kind of object leave a mark. \"Seen\" means the data shows it clearly; otherwise SpotX says so instead of guessing. Each one cites the paper it comes from."
      : s ? "No band list for this object." : "The band list appears with the spectrum.";
    ui.bandsList.replaceChildren(...fb.flatMap((b) => {
      const dt = document.createElement("dt");
      dt.textContent = `${plainName(b.molecule)} · ${b.lo}–${b.hi} µm`;
      dt.title = b.snr != null ? `${b.molecule}: ${b.snr}σ` : b.molecule;
      const st = Object.assign(document.createElement("span"), {
        className: `status ${b.status}`,
        textContent: BAND_STATUS[b.status] ?? b.status,
      });
      dt.append(st);
      const dd = Object.assign(document.createElement("dd"), { textContent: b.plain });
      dd.append(Object.assign(document.createElement("span"), { className: "ref", textContent: b.ref }));
      return [dt, dd];
    }));
    return;
  }
  ui.bandsTitle.textContent = "What the stripes mean";
  ui.bandsNote.textContent = "Glowing gases shine at their own exact colours. A stripe shows where to look, not what was found: the gas is only there if the dots rise inside it.";
  const bySubstance = new Map();
  for (const b of features.bands) bySubstance.set(b.what, [...(bySubstance.get(b.what) ?? []), b]);
  ui.bandsList.replaceChildren(...[...bySubstance].flatMap(([what, bs]) => {
    const n = bs.length;
    const dt = Object.assign(document.createElement("dt"), { textContent: `${NEBULA_GAS[what] ?? what}${n > 1 ? ` · ${n} stripes` : ""}` });
    const dd = Object.assign(document.createElement("dd"), { textContent: features.glossary[what] ?? "" });
    dd.append(Object.assign(document.createElement("span"), { className: "ref", textContent: bs.map((b) => `${b.name} ${b.center_um} µm`).join(" · ") }));
    return [dt, dd];
  }));
}

let specTimer = null;

// Never a blank chart: either a spinner with an explanation, or a message.
function specLoading(title, text, { spinner = true } = {}) {
  clearInterval(specTimer);
  if (!title) {
    ui.specLoading.hidden = true;
    return;
  }
  const box = document.createElement("div");
  if (spinner) box.append(Object.assign(document.createElement("div"), { className: "spinner" }));
  box.append(Object.assign(document.createElement("b"), { textContent: title }));
  box.append(Object.assign(document.createElement("p"), { textContent: text }));
  if (spinner) {
    const el = Object.assign(document.createElement("div"), { className: "elapsed" });
    const t0 = Date.now();
    const tick = () => {
      const sec = Math.round((Date.now() - t0) / 1000);
      el.textContent = sec < 5 ? "" : `Working… ${sec < 60 ? `${sec} s` : `${Math.floor(sec / 60)} min ${sec % 60} s`}`;
    };
    tick();
    specTimer = setInterval(tick, 1000);
    box.append(el);
  }
  ui.specLoading.replaceChildren(box);
  ui.specLoading.hidden = false;
}

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" };
const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ESCAPES[c]);

function note(html, cls = "") {
  const p = document.createElement("p");
  p.className = `note ${cls}`;
  p.innerHTML = html;
  return p;
}

async function loadSpectrum(force = false) {
  if (!obj || !ctrl) return;
  const point = isPointSource();
  const pos = spot ?? { ra: obj.ra, dec: obj.dec };
  const key = `${point}|${obj.ra},${obj.dec},${pos.ra},${pos.dec}`;
  const what = spot ? "Clicked spot" : point ? obj.name : "Field centre";
  ui.specPos.textContent = `${what}: ${formatRaDec(pos.ra, pos.dec)}`;
  ui.specCentre.hidden = !spot;
  ui.specCentre.textContent = point ? `Back to ${obj.name}` : "Use field centre";
  ui.specLede.textContent = point
    ? "A spectrum is a barcode of light: every substance glows or absorbs at its own colours. This is how bright this object is in each of SPHEREx's infrared colours."
    : "A spectrum is a barcode of light: every substance glows or absorbs at its own colours. This is how bright one spot is in each of SPHEREx's infrared colours.";
  if (!visits.length) {
    ui.specChart.replaceChildren();
    ui.specLegend.replaceChildren();
    ui.specNotes.replaceChildren();
  ui.specSci.replaceChildren();
    ui.specMsg.textContent = "";
    renderBands(null);
    if (status === "none") specLoading("No SPHEREx data here yet", "SPHEREx hasn't observed this position, so there's no spectrum to show.", { spinner: false });
    else if (status === "error") specLoading("The visit list couldn't be loaded", "Without it SpotX can't measure a spectrum. Check that the data service is running, then reopen the object.", { spinner: false });
    else specLoading("Checking SPHEREx visits…", "The spectrum starts as soon as SpotX knows when SPHEREx looked here.");
    return;
  }
  if (key === spectrumKey && !force) return;
  spectrumKey = key;
  spectrumData = null;
  renderBands(null);
  ui.specChart.replaceChildren();
  ui.specLegend.replaceChildren();
  ui.specNotes.replaceChildren();
  ui.specSci.replaceChildren();
  ui.specMsg.textContent = "";
  const exposures = visits.reduce((n, v) => n + v.n_frames, 0);
  specLoading(
    point ? `Measuring ${spot ? "this spot" : obj.name} in ${exposures} exposures…` : "Measuring every exposure at this spot…",
    point
      ? "If this object wasn't prepared in advance, SpotX first downloads small cutouts of every exposure from NASA's archive. That can take several minutes the first time; after that it opens instantly."
      : "This reuses the downloads behind the Explore images, so it's quick once they're built. If they aren't yet, it waits for them, which can take several minutes the first time.",
  );
  const my = token;
  let s;
  try {
    s = point
      ? await getPointSpectrum({ ra: pos.ra, dec: pos.dec, target: spot ? null : (obj.target_id ?? (obj.spectrum === "point" ? obj.id : null)) }, ctrl.signal)
      : await getSpectrum({ ra: pos.ra, dec: pos.dec, field_ra: obj.ra, field_dec: obj.dec, fov: obj.fov }, ctrl.signal);
  } catch (err) {
    if (err.name === "AbortError" || my !== token || key !== spectrumKey) return;
    spectrumKey = null;
    specLoading(...errorText(err), { spinner: false });
    return;
  }
  if (my !== token || key !== spectrumKey) return;
  specLoading(null);
  spectrumData = { ...s, point };
  drawSpectrumNow();
}

// Plain words for the codes in data/features.json and web/data/features.json.
const SUBSTANCE = {
  H2O: "Water", CH4: "Methane", CO: "Carbon monoxide", CO2: "Carbon dioxide", "CH4 + H2": "Methane and hydrogen",
  "H (Br-alpha)": "Hydrogen", dust: "Warm dust", "organics (C-H)": "Organic molecules", "OH / H2O": "Water",
  heat: "Its own heat", "olivine/pyroxene": "Minerals", pyroxene: "Minerals", none: "Clear window",
};
const NEBULA_GAS = { hydrogen: "Hydrogen", h2: "Hydrogen molecules", pah: "Carbon dust" };
const plainName = (m) => SUBSTANCE[m] ?? m;
const listText = (xs) => (xs.length > 1 ? `${xs.slice(0, -1).join(", ")} and ${xs.at(-1)}` : xs[0] ?? "");

// top: what everyone reads above the chart. sci: details under "For scientists".
function pointNotes(s) {
  const top = [], out = [];
  if (s.saturation_note) top.push(note(`<b>Heads-up.</b> ${esc(s.saturation_note)}`, "warn"));
  const f = s.features;
  if (f) {
    const n = f.bands.length;
    const seen = [...new Set(f.bands.filter((b) => b.status === "seen" && b.molecule !== "none").map((b) => plainName(b.molecule).toLowerCase()))];
    top.push(note(`<b>What this shows: ${esc(f.label)}.</b> ${esc(f.plain)} ${seen.length
      ? `In this light we can clearly see <b>${esc(listText(seen))}</b>.`
      : s.saturation_note
        ? "Its usual marks can't be checked well here, because most exposures were too bright to use."
        : "None of its usual marks are clear in this data: it may be too faint, or the marks too weak to call."}`, "verdict"));
    out.push(note(`<b>Band test.</b> ${f.seen} of ${n} expected band${n === 1 ? "" : "s"} seen at 3σ or more, against a power-law continuum.`));
    if (f.caveat) out.push(note(esc(f.caveat), "check"));
  }
  const w = s.w2_check;
  if (w && w.ratio != null) {
    const off = Math.abs(w.ratio - 1);
    const verdict = off <= 0.2
      ? "They agree within 20%, about as close as expected: the WISE band runs a little past where SPHEREx stops, and WISE measured it around 2010."
      : `They differ by ${Math.round(off * 100)}%, more than the ~20% expected. The object may vary, or a neighbour's light may be mixed in.`;
    const sat = w.wise_saturated ? " WISE itself saturated on this object, so its value is only a loose check." : "";
    out.push(note(`<b>Cross-check with WISE.</b> SPHEREx at 4.2–5.0 µm: ${w.spherex_mJy.toPrecision(3)} ± ${w.spherex_err.toPrecision(2)} mJy. WISE W2 (AllWISE): ${w.wise_mJy.toPrecision(3)} mJy. Ratio ${w.ratio}. ${verdict}${sat}`, off <= 0.2 ? "good" : "check"));
  }
  const b = s.blends ?? [];
  if (b.length) {
    const fitted = b.filter((x) => x.fitted).length;
    const mixed = b.length - fitted;
    const parts = [
      `${b.length} Gaia star${b.length > 1 ? "s" : ""} within ${Math.max(...b.map((x) => x.sep_arcsec))}″.`,
      fitted ? `${fitted} fitted separately.` : "",
      mixed ? `${mixed} too close to separate, so ${mixed > 1 ? "their" : "its"} light is mixed in.` : "",
    ];
    out.push(note(`<b>Nearby stars.</b> ${parts.filter(Boolean).join(" ")}`, mixed ? "check" : ""));
  }
  return { top, sci: out };
}

function nebulaNotes(s) {
  const top = s.saturation_note ? [note(`<b>Heads-up.</b> ${esc(s.saturation_note)}`, "warn")] : [];
  top.push(note(`<b>How to read this.</b> Glowing gases shine at their own exact colours, so they show up as sharp peaks. The stripes mark where to look: a peak inside a stripe means that gas is glowing at this spot in ${esc(obj.name)}. Dots that stay flat in a stripe mean it isn't, or it's too faint to tell.`, "verdict"));
  return { top, sci: [] };
}

function drawSpectrumNow() {
  const s = spectrumData;
  if (!s) return;
  renderBands(s);
  const { top, sci } = s.point ? pointNotes(s) : nebulaNotes(s);
  ui.specNotes.replaceChildren(...top);
  ui.specSci.replaceChildren(...sci);
  if (!s.points.length) {
    ui.specChart.replaceChildren();
    ui.specLegend.replaceChildren();
    ui.specMsg.textContent = "";
    specLoading(
      "No usable exposures",
      s.saturation_note ? "Every exposure saturated on this object, so there's nothing to plot. See the note above." : "The spot may sit on masked pixels or a detector edge.",
      { spinner: false },
    );
    return;
  }
  const unit = s.point ? (s.units?.flux ?? "mJy") : s.unit;
  const pts = s.points.map((p) => {
    const i = visitOfMjd(p.mjd);
    return { ...p, group: i ?? -1, color: i != null ? visits[i].color : "#999" };
  });
  const groups = [...new Set(pts.map((p) => p.group))].sort((a, b) => a - b);
  const bands = s.point
    ? (s.features?.bands ?? []).map((b) => ({
        name: plainName(b.molecule),
        lo: b.lo,
        hi: b.hi,
        status: b.status,
        title: `${b.molecule}: ${BAND_STATUS[b.status] ?? b.status}`,
      }))
    : features.bands.map((b) => ({ ...b, name: NEBULA_GAS[b.what] ?? b.name, title: `${b.name} · ${b.center_um} µm` }));
  drawSpectrum(ui.specChart, pts.filter((p) => !hiddenVisits.has(p.group)), bands, {
    yLabel: s.point ? `flux (${unit})` : `brightness (${unit})`,
    binned: s.point ? (s.binned ?? []) : [],
  });
  ui.specLegend.replaceChildren(...groups.map((g) => {
    const b = document.createElement("button");
    const v = visits[g];
    b.setAttribute("aria-pressed", String(!hiddenVisits.has(g)));
    b.innerHTML = `<i></i><span></span>`;
    b.querySelector("i").style.background = v?.color ?? "#999";
    b.querySelector("span").textContent = v ? formatRange(v.mjd_start, v.mjd_end) : "Other";
    b.title = "Show or hide this visit";
    b.addEventListener("click", () => {
      if (hiddenVisits.has(g)) hiddenVisits.delete(g);
      else if (hiddenVisits.size < groups.length - 1) hiddenVisits.add(g);
      drawSpectrumNow();
    });
    return b;
  }));
  if (s.point) {
    const ph = s.photometry ?? {};
    const how = [ph.psf && `PSF fitting on ${ph.psf}`, ph.aperture && `aperture photometry on ${ph.aperture}`].filter(Boolean).join(" and ");
    ui.specMsg.textContent = `${pts.length} exposures, coloured by visit. Flux in ${unit}${how ? `, from ${how} exposures` : ""}${ph.sys_floor ? `, with a ${Math.round(ph.sys_floor * 100)}% calibration floor on each error` : ""}. The white line is the spectrum binned to SPHEREx's resolution.`;
  } else {
    ui.specMsg.textContent = `${pts.length} exposures, coloured by visit. Surface brightness in ${unit} with zodiacal light (sunlit dust in the Solar System) removed, averaged over 3×3 pixels. Where visits overlap, they agree unless something changed.`;
  }
}

// ---------- about tab ----------

function renderAbout() {
  const o = obj;
  if (!o) return;
  const k = KINDS[o.kind] ?? KINDS.unknown;
  ui.aboutName.textContent = o.name;
  ui.aboutKind.textContent = k.label;
  ui.aboutText.textContent = k.about;
  ui.aboutTime.textContent = k.overTime;

  const facts = [];
  if (o.aliases?.length) facts.push(["Also known as", o.aliases.join(", ")]);
  if (o.simbad_type) facts.push(["Catalog type", SIMBAD_TYPES[o.simbad_type] ? `${SIMBAD_TYPES[o.simbad_type]} (${o.simbad_type})` : o.simbad_type]);
  facts.push(["Position", `${formatRaDec(o.ra, o.dec)}\n(RA ${o.ra.toFixed(4)}°, Dec ${o.dec.toFixed(4)}°${o.coord_epoch ? `, where it is in ${o.coord_epoch}` : ""})`]);
  if (o.constellation) facts.push(["Constellation", o.constellation]);
  if (o.size_arcmin) facts.push(["Apparent size", `${o.size_arcmin}′ across`]);
  const fieldArcmin = Math.round(o.fov * 60);
  facts.push(["Field shown", o.size_arcmin && o.size_arcmin > fieldArcmin
    ? `${fieldArcmin}′ square, centred on it. The object is bigger than this, so you see its central part.`
    : `${fieldArcmin}′ square, centred on it`]);
  if (o.pm_mas_yr) facts.push(["Motion on the sky", `${(Math.hypot(...o.pm_mas_yr) / 1000).toFixed(2)}″ per year`]);
  if (visits.length) facts.push(["SPHEREx visits", `${visits.length}, from ${formatDate(visits[0].mjd_start)} to ${formatDate(visits.at(-1).mjd_end)}`]);
  else if (o.visits?.n === 0) facts.push(["SPHEREx visits", "None yet"]);
  facts.push(["Data", `Images: NASA/JPL-Caltech/IPAC SPHEREx via IRSA. Position and type: ${o.source ?? "SIMBAD"}.`]);

  ui.aboutFacts.replaceChildren(...facts.flatMap(([t, d]) => {
    const dd = Object.assign(document.createElement("dd"), { textContent: d });
    dd.style.whiteSpace = "pre-line";
    return [Object.assign(document.createElement("dt"), { textContent: t }), dd];
  }));
  const links = [];
  if (o.simbad_id) links.push([`SIMBAD entry`, `https://simbad.cds.unistra.fr/simbad/sim-id?Ident=${encodeURIComponent(o.simbad_id)}`]);
  links.push(["SPHEREx at IRSA", "https://irsa.ipac.caltech.edu/Missions/spherex.html"]);
  ui.aboutLinks.replaceChildren(...links.map(([t, href]) => Object.assign(document.createElement("a"), { textContent: t, href, target: "_blank", rel: "noopener" })));
}

// ---------- boot ----------

function wire() {
  ui.homeLink.addEventListener("click", showHome);
  for (const t of ui.tabs) {
    t.addEventListener("click", () => setTab(t.dataset.tab));
    t.addEventListener("keydown", (e) => {
      const i = ui.tabs.indexOf(t);
      const j = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : null;
      if (j == null) return;
      e.preventDefault();
      const next = ui.tabs[(j + ui.tabs.length) % ui.tabs.length];
      next.focus();
      setTab(next.dataset.tab);
    });
  }
  for (const b of ui.viewButtons) b.addEventListener("click", () => setView(b.dataset.view));
  ui.play.addEventListener("click", togglePlay);
  ui.knownToggle.addEventListener("click", toggleKnown);
  ui.pickA.addEventListener("change", () => onPairChange("a", ui.pickA.value));
  ui.pickB.addEventListener("change", () => onPairChange("b", ui.pickB.value));
  paneA.el.addEventListener("click", (e) => onPaneClick(e, paneA));
  paneB.el.addEventListener("click", (e) => onPaneClick(e, paneB));
  ui.spotClose.addEventListener("click", closeSpot);
  ui.spotSpectrum.addEventListener("click", () => setTab("spectrum"));
  ui.specCentre.addEventListener("click", () => { spot = null; closeSpot(); loadSpectrum(); });
  setupSwipe();

  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, select, textarea, [role=slider]") || ui.object.hidden || state.tab !== "explore") return;
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      const dir = e.key === "ArrowRight" ? 1 : -1;
      e.preventDefault();
      if (state.view === "sequence") {
        stop();
        step(dir);
      } else if (isCompare()) {
        const ids = withImage().filter((i) => i !== state.a);
        if (!ids.length) return;
        const k = ids.indexOf(state.b);
        state.b = ids[(k + dir + ids.length) % ids.length];
        renderPair();
      }
      renderTrack();
      refresh();
      syncUrl();
    } else if (e.key === " " && !e.target.closest("button")) {
      e.preventDefault();
      togglePlay();
    } else if (e.key === "Escape") {
      closeSpot();
    }
  });

  setupSearch({
    input: $("search-input"),
    list: $("search-results"),
    getCatalog: () => catalog,
    onPick: (o) => openObject(o),
    onLookup: lookup,
    allowLookup: () => !demoMode,
  });
}

async function init() {
  if (new URLSearchParams(location.search).has("embed")) document.body.classList.add("embed");
  wire();
  const route = readState();
  let ids;
  [catalog, features, ids] = await Promise.all([
    getCatalog().catch(() => []),
    getFeatures().catch(() => features),
    snapshotIds(),
  ]);
  // Demo edition (static snapshot, e.g. on Netlify): list only what it includes.
  demoMode = Boolean(ids);
  if (demoMode) catalog = catalog.filter((o) => ids.has(o.id));
  // The known-objects overlay queries live star and asteroid catalogues: not in the snapshot.
  if (demoMode) ui.knownToggle.hidden = true;
  renderCatalog();
  if (demoMode) {
    ui.catalog.prepend(Object.assign(document.createElement("p"), {
      className: "demo-note",
      textContent: `Demo edition: ${catalog.length} objects, with real SPHEREx data prepared in advance. The full version, with every object and name lookup, runs on SpotX's Python server.`,
    }));
  }
  renderBands();
  const known = catalog.find((o) => o.id === route.objectId);
  if (known) {
    openObject(known, route);
  } else if (route.custom) {
    const c = route.custom;
    openObject({ custom: true, name: c.name ?? `RA ${c.ra}, Dec ${c.dec}`, ra: c.ra, dec: c.dec, fov: c.fov ?? 0.2, kind: "unknown", source: "link" }, route);
  } else {
    showHome();
  }
}

init();
