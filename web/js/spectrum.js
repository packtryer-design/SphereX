// Dependency-free SVG charts: a spectrum (brightness vs wavelength) and a time series.
const NS = "http://www.w3.org/2000/svg";

function el(name, attrs = {}, text) {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text != null) node.textContent = text;
  return node;
}

function yRange(points) {
  const lo = Math.min(0, ...points.map((p) => p.flux - (p.err ?? 0)));
  const hi = Math.max(...points.map((p) => p.flux + (p.err ?? 0)));
  const pad = (hi - lo) * 0.08 || 1;
  return [lo - (lo < 0 ? pad : 0), hi + pad];
}

function niceTicks(lo, hi, n = 4) {
  const step0 = (hi - lo) / n;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= step0) ?? step0;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(Math.round(v / step) * step);
  return out;
}

function fmtNum(v) {
  const a = Math.abs(v);
  if (a >= 100 || v === 0) return v.toFixed(0);
  if (a >= 1) return v.toFixed(1);
  return v.toPrecision(2);
}

function groupBy(points) {
  const m = new Map();
  for (const p of points) {
    const k = p.group ?? 0;
    if (!m.has(k)) m.set(k, []);
    m.get(k).push(p);
  }
  return m;
}

// SPHEREx resolving power by wavelength: a line lands in a band about lambda / R wide.
export const resolvingPower = (um) => (um < 2.42 ? 41 : um < 3.82 ? 35 : um < 4.42 ? 110 : 130);

// points: [{wavelength_um, flux, err, group, color}]
// bands:  [{name, center_um}] (shaded at SPHEREx resolution) or [{name, lo, hi, status}]
// binned: optional [{wavelength_um, flux, err}], drawn as a bold line over the points
export function drawSpectrum(container, points, bands = [], { yLabel = "brightness", W = 640, H = 300, binned = [] } = {}) {
  const PAD = { l: 52, r: 12, t: 30, b: 36 };
  const X_MIN = 0.7, X_MAX = 5.05;
  const [yLo, yHi] = yRange(points.length ? points : binned);
  const x = (w) => PAD.l + ((w - X_MIN) / (X_MAX - X_MIN)) * (W - PAD.l - PAD.r);
  const y = (f) => H - PAD.b - ((f - yLo) / (yHi - yLo)) * (H - PAD.t - PAD.b);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${yLabel} by wavelength` });

  bands.forEach((b, i) => {
    const half = (b.center_um ?? 1) / resolvingPower(b.center_um ?? 1) / 2;
    const x0 = x(b.lo ?? b.center_um - half), x1 = x(b.hi ?? b.center_um + half);
    const rect = el("rect", { class: `band ${b.status ?? ""}`, x: x0, y: PAD.t, width: Math.max(x1 - x0, 2), height: H - PAD.t - PAD.b });
    if (b.title) rect.append(el("title", {}, b.title));
    svg.append(rect);
    svg.append(el("text", { class: "band-label", x: (x0 + x1) / 2, y: PAD.t - 4 - (i % 2) * 11, "text-anchor": "middle" }, b.name));
  });

  svg.append(el("line", { class: "axis", x1: PAD.l, y1: H - PAD.b, x2: W - PAD.r, y2: H - PAD.b }));
  svg.append(el("line", { class: "axis", x1: PAD.l, y1: PAD.t, x2: PAD.l, y2: H - PAD.b }));
  if (yLo < 0) svg.append(el("line", { class: "zero", x1: PAD.l, y1: y(0), x2: W - PAD.r, y2: y(0) }));
  for (let w = 1; w <= 5; w++) svg.append(el("text", { class: "tick", x: x(w), y: H - PAD.b + 14, "text-anchor": "middle" }, w));
  for (const v of niceTicks(yLo, yHi)) svg.append(el("text", { class: "tick", x: PAD.l - 6, y: y(v) + 3, "text-anchor": "end" }, fmtNum(v)));
  svg.append(el("text", { class: "tick", x: (PAD.l + W - PAD.r) / 2, y: H - 4, "text-anchor": "middle" }, "wavelength (µm)"));
  const yMid = (PAD.t + H - PAD.b) / 2;
  svg.append(el("text", { class: "tick", x: 11, y: yMid, "text-anchor": "middle", transform: `rotate(-90 11 ${yMid})` }, yLabel));

  for (const pts of groupBy(points).values()) {
    const sorted = [...pts].sort((a, b) => a.wavelength_um - b.wavelength_um);
    const color = sorted[0]?.color ?? "currentColor";
    if (sorted.length > 1) {
      const d = sorted.map((p, i) => `${i ? "L" : "M"}${x(p.wavelength_um).toFixed(1)} ${y(p.flux).toFixed(1)}`).join(" ");
      svg.append(el("path", { class: "line", stroke: color, d }));
    }
    for (const p of sorted) {
      if (p.err) svg.append(el("line", { class: "err", x1: x(p.wavelength_um), x2: x(p.wavelength_um), y1: y(p.flux - p.err), y2: y(p.flux + p.err) }));
      svg.append(el("circle", { cx: x(p.wavelength_um), cy: y(p.flux), r: points.length > 40 ? 2 : 3.5, fill: color }));
    }
  }
  if (binned.length > 1) {
    const sorted = [...binned].sort((a, b) => a.wavelength_um - b.wavelength_um);
    const d = sorted.map((p, i) => `${i ? "L" : "M"}${x(p.wavelength_um).toFixed(1)} ${y(p.flux).toFixed(1)}`).join(" ");
    svg.append(el("path", { class: "binned", d }));
  }
  container.replaceChildren(svg);
}

// points: [{mjd, flux, err, color, label}]: brightness at one spot, one point per visit.
export function drawSeries(container, points, { yLabel = "brightness", W = 320, H = 170 } = {}) {
  const PAD = { l: 38, r: 14, t: 12, b: 34 };
  const t0 = Math.min(...points.map((p) => p.mjd)), t1 = Math.max(...points.map((p) => p.mjd));
  const span = t1 - t0 || 1;
  const [yLo, yHi] = yRange(points);
  const x = (t) => (points.length === 1 ? (PAD.l + W - PAD.r) / 2 : PAD.l + ((t - t0) / span) * (W - PAD.l - PAD.r));
  const y = (f) => H - PAD.b - ((f - yLo) / (yHi - yLo)) * (H - PAD.t - PAD.b);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${yLabel} at each visit` });
  svg.append(el("line", { class: "axis", x1: PAD.l, y1: H - PAD.b, x2: W - PAD.r, y2: H - PAD.b }));
  svg.append(el("line", { class: "axis", x1: PAD.l, y1: PAD.t, x2: PAD.l, y2: H - PAD.b }));
  for (const v of niceTicks(yLo, yHi, 3)) svg.append(el("text", { class: "tick", x: PAD.l - 5, y: y(v) + 3, "text-anchor": "end" }, fmtNum(v)));
  const sorted = [...points].sort((a, b) => a.mjd - b.mjd);
  const d = sorted.map((p, i) => `${i ? "L" : "M"}${x(p.mjd).toFixed(1)} ${y(p.flux).toFixed(1)}`).join(" ");
  svg.append(el("path", { class: "line", stroke: "currentColor", d }));
  sorted.forEach((p, i) => {
    if (p.err) svg.append(el("line", { class: "err", x1: x(p.mjd), x2: x(p.mjd), y1: y(p.flux - p.err), y2: y(p.flux + p.err) }));
    svg.append(el("circle", { cx: x(p.mjd), cy: y(p.flux), r: 4, fill: p.color ?? "currentColor" }));
    const last = sorted.length - 1;
    const anchor = sorted.length > 1 && i === 0 ? "start" : sorted.length > 1 && i === last ? "end" : "middle";
    if (sorted.length <= 6 || i === 0 || i === last) {
      svg.append(el("text", { class: "tick", x: x(p.mjd), y: H - PAD.b + 14, "text-anchor": anchor }, p.label ?? ""));
    }
  });
  container.replaceChildren(svg);
}
