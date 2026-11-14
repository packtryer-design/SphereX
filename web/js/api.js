// The only file that knows where data comes from.
//   data/objects.json   the searchable catalog (built from SIMBAD + IRSA by scripts/build_objects.py)
//   /api/...            the Python API (same origin by default; override with ?api=http://host:8000)

export const API_BASE = (new URLSearchParams(location.search).get("api") ?? "").replace(/\/$/, "");

export class OfflineError extends Error {}

async function getJSON(url, signal) {
  let res;
  try {
    res = await fetch(url, { signal });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new OfflineError("Blink's data service can't be reached.");
  }
  const isJSON = (res.headers.get("content-type") ?? "").includes("json");
  if (!isJSON) throw new OfflineError("Blink's data service isn't running here.");
  const body = await res.json();
  if (!res.ok) {
    const err = new Error(typeof body.detail === "string" ? body.detail : `${res.status} ${res.statusText}`);
    err.status = res.status;
    throw err;
  }
  return body;
}

const api = (path, query) => {
  const q = Object.fromEntries(Object.entries(query).filter(([, v]) => v != null));
  return `${API_BASE}/api/${path}?${new URLSearchParams(q)}`;
};

export const getCatalog = () => getJSON("data/objects.json").then((d) => d.objects);
export const getFeatures = () => getJSON("data/features.json");

// Real SPHEREx visit dates for a position. Fast: no image downloads.
export const getVisits = ({ ra, dec }, signal) => getJSON(api("visits", { ra, dec }), signal);

// mode: epoch (one image per visit) | diff (each visit minus `ref`) | rgb (3 visits as R,G,B) | single
export async function getFrames({ ra, dec, fov, mode, ref }, signal) {
  const data = await getJSON(api("frames", { ra, dec, fov, mode, ref }), signal);
  const base = `${API_BASE || location.origin}/`;
  data.frames = data.frames.map((f) => ({ ...f, png: new URL(f.png, base).href }));
  return data;
}

// Surface-brightness spectrum at (ra, dec), right for nebulae, reusing the open field's
// cutouts (field_ra, field_dec, fov). /api/spectrum is Person C's aperture photometry for stars.
export const getSpectrum = (q, signal) => getJSON(api("surface-spectrum", q), signal);

// Point sources (stars, brown dwarfs): Person C's PSF photometry in mJy, plus molecule bands,
// saturation note, WISE W2 check and blends. `target` (a data/targets.json id) adds proper
// motion and the band profile.
export const getPointSpectrum = ({ ra, dec, target }, signal) =>
  getJSON(api("spectrum", { ra, dec, target }), signal);

export const resolveName = (name, signal) => getJSON(api("resolve", { name }), signal);
