// One image slot that crossfades: the new image decodes off screen, fades in on top, and the
// old one is dropped once it's covered. Every visit is on the same pixel grid, so a crossfade
// is a true before/after with nothing shifting.
export class Pane {
  constructor(el) {
    this.el = el;
    this.layers = [...el.querySelectorAll("img.layer")];
    this.label = el.querySelector(".pane-label");
    this.front = 0;
    this.src = null;
    this.seq = 0;
    this.timer = null;
  }

  get img() {
    return this.layers[this.front];
  }

  async show(src, alt = "", fadeMs = 450) {
    if (src === this.src) {
      this.img.alt = alt;
      return;
    }
    this.src = src;
    const seq = ++this.seq;
    const back = this.layers[1 - this.front];
    const front = this.layers[this.front];
    back.src = src;
    back.alt = alt;
    try {
      await back.decode();
    } catch {
      /* broken image: still swap so the old one doesn't linger */
    }
    if (seq !== this.seq) return; // a newer image was asked for meanwhile
    this.el.style.setProperty("--fade", `${fadeMs}ms`);
    back.style.zIndex = 2;
    front.style.zIndex = 1;
    back.classList.add("on");
    this.front = 1 - this.front;
    clearTimeout(this.timer);
    this.timer = setTimeout(() => front.classList.remove("on"), fadeMs + 30);
  }

  clear() {
    this.src = null;
    this.seq++;
    for (const l of this.layers) {
      l.classList.remove("on");
      l.removeAttribute("src");
    }
  }

  setLabel(text) {
    if (this.label) this.label.textContent = text;
  }

  // Where the picture actually sits inside the pane (object-fit: contain letterboxes it).
  imageRect() {
    const img = this.img;
    const box = this.el.getBoundingClientRect();
    if (!img.naturalWidth) return null;
    const scale = Math.min(box.width / img.naturalWidth, box.height / img.naturalHeight);
    const w = img.naturalWidth * scale, h = img.naturalHeight * scale;
    return { left: box.left + (box.width - w) / 2, top: box.top + (box.height - h) / 2, width: w, height: h };
  }
}

// Sky position of a point on the image. The API draws every field on a TAN grid centred on
// the object, north up and east left, at 6.15"/pixel (api/imaging/pipeline.py: target_grid).
const PIXEL_ARCSEC = 6.15;
const gridDeg = (fov) => ((Math.ceil((fov * 3600) / PIXEL_ARCSEC) | 1) * PIXEL_ARCSEC) / 3600;
export function skyAt(field, fx, fy) {
  const deg = gridDeg(field.fov);
  const dec = field.dec + (0.5 - fy) * deg;
  let ra = field.ra - ((fx - 0.5) * deg) / Math.cos((field.dec * Math.PI) / 180);
  ra = ((ra % 360) + 360) % 360;
  return { ra: Math.round(ra * 1e5) / 1e5, dec: Math.round(dec * 1e5) / 1e5 };
}

// The inverse of skyAt: where (ra, dec) falls on the image, as fractions (0..1, top-left origin).
export function fracAt(field, ra, dec) {
  const deg = gridDeg(field.fov);
  const dra = ((((ra - field.ra) % 360) + 540) % 360) - 180; // across RA = 0/360
  return { fx: 0.5 - (dra * Math.cos((field.dec * Math.PI) / 180)) / deg, fy: 0.5 - (dec - field.dec) / deg };
}

export function formatRaDec(ra, dec) {
  const pad = (x, w = 2) => String(x).padStart(w, "0");
  const h = ra / 15;
  const hh = Math.floor(h), mm = Math.floor((h - hh) * 60), ss = ((h - hh) * 60 - mm) * 60;
  const d = Math.abs(dec);
  const dd = Math.floor(d), dm = Math.floor((d - dd) * 60), ds = ((d - dd) * 60 - dm) * 60;
  const sign = dec < 0 ? "−" : "+";
  return `${pad(hh)}h ${pad(mm)}m ${ss.toFixed(1).padStart(4, "0")}s, ${sign}${pad(dd)}° ${pad(dm)}′ ${pad(ds.toFixed(0))}″`;
}
