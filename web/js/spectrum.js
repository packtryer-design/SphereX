// Small dependency-free SVG chart: brightness vs wavelength with known bands shaded.
// Works for a handful of layer samples now and ~102 backend points later.
const W = 340, H = 220, PAD = { l: 36, r: 10, t: 26, b: 32 };
const X_MIN = 0.75, X_MAX = 5.0;
const NS = "http://www.w3.org/2000/svg";

function el(name, attrs = {}, text) {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text != null) node.textContent = text;
  return node;
}

export function drawSpectrum(container, points, bands, yLabel = "brightness") {
  const yMax = Math.max(...points.map((p) => p.flux + (p.err ?? 0))) * 1.1 || 1;
  const x = (w) => PAD.l + ((w - X_MIN) / (X_MAX - X_MIN)) * (W - PAD.l - PAD.r);
  const y = (f) => H - PAD.b - (Math.max(f, 0) / yMax) * (H - PAD.t - PAD.b);
  const yMid = (PAD.t + H - PAD.b) / 2;

  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${yLabel} by wavelength` });

  bands.forEach((b, i) => {
    const x0 = x(b.center_um - b.width_um / 2), x1 = x(b.center_um + b.width_um / 2);
    svg.append(el("rect", { class: `band ${b.kind}`, x: x0, y: PAD.t, width: Math.max(x1 - x0, 2), height: H - PAD.t - PAD.b }));
    // Two label rows so neighbours don't overlap.
    svg.append(el("text", { class: "band-label", x: (x0 + x1) / 2, y: PAD.t - 4 - (i % 2) * 10, "text-anchor": "middle" }, b.name));
  });

  svg.append(el("line", { class: "axis", x1: PAD.l, y1: H - PAD.b, x2: W - PAD.r, y2: H - PAD.b }));
  svg.append(el("line", { class: "axis", x1: PAD.l, y1: PAD.t, x2: PAD.l, y2: H - PAD.b }));
  for (let w = 1; w <= 5; w++) svg.append(el("text", { class: "tick", x: x(w), y: H - PAD.b + 13, "text-anchor": "middle" }, w));
  svg.append(el("text", { class: "tick", x: (PAD.l + W - PAD.r) / 2, y: H - 3, "text-anchor": "middle" }, "wavelength (µm)"));
  svg.append(el("text", { class: "tick", x: 10, y: yMid, "text-anchor": "middle", transform: `rotate(-90 10 ${yMid})` }, yLabel));

  const sorted = [...points].sort((a, b) => a.wavelength_um - b.wavelength_um);
  svg.append(el("path", { class: "line", d: sorted.map((p, i) => `${i ? "L" : "M"}${x(p.wavelength_um)} ${y(p.flux)}`).join(" ") }));
  for (const p of sorted) {
    if (p.err) svg.append(el("line", { class: "err", x1: x(p.wavelength_um), x2: x(p.wavelength_um), y1: y(p.flux - p.err), y2: y(p.flux + p.err) }));
    svg.append(el("circle", { cx: x(p.wavelength_um), cy: y(p.flux), r: points.length > 20 ? 1.8 : 4, fill: p.tint ?? "currentColor" }));
  }

  container.replaceChildren(svg);
}
