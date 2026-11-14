// The only file that knows where data comes from.

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${url}`);
  return res.json();
}

// ---------- now: static NASA layer stacks in web/data/ ----------

export const getDatasets = () => getJSON("data/datasets.json").then((d) => d.datasets);
export const getFeatures = () => getJSON("data/features.json");

// A "layer" is one image of the field in one color. Image paths in layers.json are
// relative to the dataset folder.
export async function getLayers(id) {
  const base = `data/${id}/`;
  const field = await getJSON(`${base}layers.json`);
  field.layers = field.layers.map((l) => ({ ...l, png: new URL(l.png, new URL(base, location.href)).href }));
  return field;
}

// ---------- later: the Python API (see docs/PLAN.md, "API contract") ----------
// Frames from /api/frames have the same shape as layers (png + wavelength_um), plus mjd and
// epoch, so they plug into the same viewer. Enable with ?api=http://localhost:8000
export const API_BASE = new URLSearchParams(location.search).get("api");

export async function getFrames({ ra, dec, fov, mode }) {
  const data = await getJSON(`${API_BASE}/api/frames?${new URLSearchParams({ ra, dec, fov, mode })}`);
  data.frames = data.frames.map((f) => ({ ...f, png: new URL(f.png, API_BASE).href }));
  return data;
}

export const getSpectrum = ({ ra, dec }) =>
  getJSON(`${API_BASE}/api/spectrum?${new URLSearchParams({ ra, dec })}`);
