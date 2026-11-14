import { getDatasets, getLayers, getFeatures } from "./api.js";
import { readState, writeState } from "./state.js";
import { sampleLayers } from "./sample.js";
import { drawSpectrum } from "./spectrum.js";

const $ = (id) => document.getElementById(id);
const ui = {
  app: $("app"), rail: $("rail"), railToggle: $("rail-toggle"), fields: $("fields"),
  fieldName: $("field-name"), credit: $("credit"),
  flip: $("flip"), img: $("frame"), marker: $("marker"), stack: $("stack"), hint: $("hint"), msg: $("msg"),
  info: $("info"), infoClose: $("info-close"), spectrum: $("spectrum"),
  spectrumLabel: $("spectrum-label"), spectrumNote: $("spectrum-note"),
  play: $("play"), blink: $("blink"), ticks: $("ticks"), now: $("now"),
  viewButtons: document.querySelectorAll("[data-view]"),
};

const state = readState();
let layers = [];
let features = { bands: [], glossary: {} };
let timer = null; // shared by play and blink
let blinkBase = 0;

const um = (w) => `${Number.isInteger(w) ? w.toFixed(1) : w} µm`;
const layerName = (l) => `${um(l.wavelength_um)}${l.feature ? ` · ${l.feature}` : ""}`;

// ---------- fields ----------

async function loadField(id) {
  stopAnimation();
  closeInfo();
  showMessage("Loading…");
  try {
    const field = await getLayers(id);
    state.field = id;
    layers = field.layers;
    layers.forEach((l) => { new Image().src = l.png; }); // preload so flipping is instant
    state.layer = Math.min(state.layer, layers.length - 1);
    ui.fieldName.textContent = field.name;
    ui.credit.textContent = field.credit ?? "";
    ui.fields.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.id === id));
    renderTicks();
    renderStack();
    showMessage(null);
    showLayer(state.layer);
  } catch (err) {
    console.error(err);
    showMessage(`Couldn't load this field. ${err.message}`);
  }
}

function showMessage(text) {
  ui.msg.hidden = !text;
  ui.msg.textContent = text ?? "";
}

// ---------- layers: bottom ticks, flip view, stack view ----------

function renderTicks() {
  ui.ticks.replaceChildren(...layers.map((l, i) => {
    const b = document.createElement("button");
    b.textContent = layerName(l);
    b.style.setProperty("--tint", l.tint);
    b.addEventListener("click", () => { stopAnimation(); showLayer(i); });
    return b;
  }));
}

function renderStack() {
  ui.stack.replaceChildren(...layers.map((l, i) => {
    const card = document.createElement("button");
    card.className = "card";
    card.style.setProperty("--i", i);
    card.innerHTML = `<span class="wl"></span><img alt=""><span class="feat"></span>`;
    card.querySelector(".wl").textContent = um(l.wavelength_um);
    card.querySelector(".wl").style.color = l.tint;
    card.querySelector(".feat").textContent = l.feature ?? "";
    card.querySelector(".feat").style.color = l.tint;
    card.querySelector("img").src = l.png;
    card.addEventListener("click", () => { showLayer(i); setView("flip"); });
    return card;
  }));
}

function showLayer(i) {
  if (!layers.length) return;
  state.layer = (i + layers.length) % layers.length;
  const l = layers[state.layer];
  ui.img.src = l.png;
  ui.img.alt = `The field at ${layerName(l)}`;
  ui.now.textContent = layerName(l);
  ui.ticks.querySelectorAll("button").forEach((b, j) => b.classList.toggle("active", j === state.layer));
  ui.stack.querySelectorAll(".card").forEach((c, j) => c.classList.toggle("active", j === state.layer));
  writeState(state);
}

function setView(view) {
  state.view = view;
  ui.flip.hidden = view !== "flip";
  ui.stack.hidden = view !== "stack";
  ui.hint.hidden = view !== "flip" || !ui.marker.hidden;
  ui.viewButtons.forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  writeState(state);
}

// ---------- play / blink ----------

function stopAnimation() {
  clearInterval(timer);
  timer = null;
  ui.play.textContent = "▶";
  ui.play.setAttribute("aria-label", "Play");
  ui.blink.setAttribute("aria-pressed", "false");
}

function togglePlay() {
  const playing = timer && ui.blink.getAttribute("aria-pressed") === "false";
  stopAnimation();
  if (playing) return;
  timer = setInterval(() => showLayer(state.layer + 1), 700);
  ui.play.textContent = "❚❚";
  ui.play.setAttribute("aria-label", "Pause");
}

function toggleBlink() {
  const blinking = ui.blink.getAttribute("aria-pressed") === "true";
  stopAnimation();
  if (blinking) return;
  blinkBase = state.layer;
  timer = setInterval(() => showLayer(state.layer === blinkBase ? blinkBase + 1 : blinkBase), 400);
  ui.blink.setAttribute("aria-pressed", "true");
}

// ---------- click → colors at this spot ----------

// Where the image actually sits inside the <img> box (object-fit: contain letterboxes it).
function imageRect() {
  const box = ui.img.getBoundingClientRect();
  const scale = Math.min(box.width / ui.img.naturalWidth, box.height / ui.img.naturalHeight);
  const w = ui.img.naturalWidth * scale, h = ui.img.naturalHeight * scale;
  return { left: box.left + (box.width - w) / 2, top: box.top + (box.height - h) / 2, width: w, height: h };
}

async function onImageClick(e) {
  const r = imageRect();
  const fx = (e.clientX - r.left) / r.width;
  const fy = (e.clientY - r.top) / r.height;
  if (fx < 0 || fx > 1 || fy < 0 || fy > 1) return; // clicked the letterbox

  const box = ui.flip.getBoundingClientRect();
  ui.marker.style.left = `${e.clientX - box.left}px`;
  ui.marker.style.top = `${e.clientY - box.top}px`;
  ui.marker.hidden = false;
  ui.hint.hidden = true;
  openInfo();

  try {
    const points = await sampleLayers(layers, fx, fy);
    drawSpectrum(ui.spectrum, points, features.bands, "relative brightness");
    describe(points);
  } catch (err) {
    console.error(err);
    ui.spectrumLabel.textContent = "";
    ui.spectrumNote.textContent = `Couldn't read the layers. ${err.message}`;
  }
}

// Plain-language summary: which layer this spot stands out in most.
// TODO (with C): replace with the real classifier / labels from features.json.
function describe(points) {
  const mean = points.reduce((a, p) => a + p.flux, 0) / points.length;
  const peak = points.reduce((best, p, i) => (p.flux > points[best].flux ? i : best), 0);
  const l = layers[peak];
  if (points[peak].flux < mean * 1.15) {
    ui.spectrumLabel.textContent = "About the same in every color";
    ui.spectrumNote.textContent = "";
    return;
  }
  ui.spectrumLabel.textContent = `Brightest at ${layerName(l)}`;
  ui.spectrumNote.textContent = features.glossary?.[l.feature] ?? "";
}

function openInfo() {
  ui.info.hidden = false;
  ui.app.classList.add("info-open");
}

function closeInfo() {
  ui.info.hidden = true;
  ui.app.classList.remove("info-open");
  ui.marker.hidden = true;
}

// ---------- boot ----------

async function init() {
  if (new URLSearchParams(location.search).has("embed")) document.body.classList.add("embed");

  const [datasets, feats] = await Promise.all([getDatasets(), getFeatures().catch(() => features)]);
  features = feats;
  ui.fields.replaceChildren(...datasets.map((d) => {
    const li = document.createElement("li");
    const b = document.createElement("button");
    b.textContent = d.name;
    b.dataset.id = d.id;
    b.addEventListener("click", () => { state.layer = 0; loadField(d.id); ui.rail.classList.remove("open"); });
    li.append(b);
    return li;
  }));

  ui.viewButtons.forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));
  ui.img.addEventListener("click", onImageClick);
  ui.infoClose.addEventListener("click", closeInfo);
  ui.play.addEventListener("click", togglePlay);
  ui.blink.addEventListener("click", toggleBlink);
  ui.railToggle.addEventListener("click", () => {
    const open = ui.rail.classList.toggle("open");
    ui.railToggle.setAttribute("aria-expanded", open);
  });
  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, select, textarea")) return;
    if (e.key === "ArrowRight") { stopAnimation(); showLayer(state.layer + 1); }
    else if (e.key === "ArrowLeft") { stopAnimation(); showLayer(state.layer - 1); }
    else if (e.key === " ") { e.preventDefault(); togglePlay(); }
    else if (e.key === "b") toggleBlink();
    else if (e.key === "f") setView("flip");
    else if (e.key === "s") setView("stack");
    else if (e.key === "Escape") { closeInfo(); ui.rail.classList.remove("open"); }
  });

  setView(state.view);
  const known = datasets.some((d) => d.id === state.field);
  await loadField(known ? state.field : datasets[0].id);
}

init();
