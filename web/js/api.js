// The only file that knows where data comes from.
//   data/objects.json   the searchable catalog (built from SIMBAD + IRSA by scripts/build_objects.py)
//   /api/...            the Python API, found at runtime (see apiBase below)

const params = new URLSearchParams(location.search);
const OVERRIDE = (params.get("api") ?? "").replace(/\/$/, "");

// Where scripts/host.py publishes the address of whichever computer is hosting the API right
// now (a free Cloudflare tunnel, so it changes each session). Read live, so the static site
// (Vercel) never needs redeploying when the host changes.
const REPO = "packtryer-design/SphereX";
const ENDPOINT_BRANCH = "api-endpoint";
const ENDPOINT_SOURCES = [
  { url: `https://api.github.com/repos/${REPO}/contents/endpoint.json?ref=${ENDPOINT_BRANCH}`, headers: { Accept: "application/vnd.github.raw+json" } },
  { url: `https://raw.githubusercontent.com/${REPO}/${ENDPOINT_BRANCH}/endpoint.json`, headers: {} },
];

export class OfflineError extends Error {
  constructor(message, { hosted = false } = {}) {
    super(message);
    this.hosted = hosted; // true: the public site, waiting for someone to run scripts/host.py
  }
}

async function alive(base) {
  try {
    const res = await fetch(`${base}/api/health`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
    return res.ok && (res.headers.get("content-type") ?? "").includes("json");
  } catch {
    return false;
  }
}

async function published() {
  for (const src of ENDPOINT_SOURCES) {
    try {
      const sep = src.url.includes("?") ? "&" : "?";
      const res = await fetch(`${src.url}${sep}t=${Date.now()}`, { cache: "no-store", headers: src.headers });
      if (res.ok) return await res.json();
    } catch {
      /* try the next source */
    }
  }
  return null;
}

async function findApi() {
  if (OVERRIDE) return OVERRIDE;
  if (await alive("")) return ""; // this page is served by the API itself (make serve, Docker, the tunnel)
  const ep = await published();
  if (ep?.status === "online" && ep.url && (await alive(ep.url))) return ep.url.replace(/\/$/, "");
  throw new OfflineError(
    ep?.status === "online"
      ? "The computer hosting Blink's data has stopped answering."
      : "Blink's data server is offline right now.",
    { hosted: true },
  );
}

// Found once, then reused. A failure is forgotten, so the next request looks again: the host
// may have come back, or moved to another computer.
let basePromise = null;
export function apiBase() {
  basePromise ??= findApi().catch((err) => {
    basePromise = null;
    throw err;
  });
  return basePromise;
}

async function getJSON(url, signal, { fromApi = false } = {}) {
  let res;
  try {
    res = await fetch(url, { signal });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    if (fromApi) basePromise = null; // the host may have changed: look it up again next time
    throw new OfflineError("Blink's data server can't be reached.", { hosted: fromApi && !OVERRIDE });
  }
  const isJSON = (res.headers.get("content-type") ?? "").includes("json");
  if (!isJSON) {
    if (fromApi) basePromise = null;
    throw new OfflineError("Blink's data server isn't answering.", { hosted: fromApi && !OVERRIDE });
  }
  const body = await res.json();
  if (!res.ok) {
    const err = new Error(typeof body.detail === "string" ? body.detail : `${res.status} ${res.statusText}`);
    err.status = res.status;
    throw err;
  }
  return body;
}

async function fromApi(path, query, signal) {
  const q = Object.fromEntries(Object.entries(query).filter(([, v]) => v != null));
  return getJSON(`${await apiBase()}/api/${path}?${new URLSearchParams(q)}`, signal, { fromApi: true });
}

// Turn an API path like /cache/png/x.png into a full URL on the API's host.
export async function apiUrl(path) {
  return new URL(path, `${(await apiBase()) || location.origin}/`).href;
}

export const getCatalog = () => getJSON("data/objects.json").then((d) => d.objects);
export const getFeatures = () => getJSON("data/features.json");

// Real SPHEREx visit dates for a position. Fast: no image downloads.
export const getVisits = ({ ra, dec }, signal) => fromApi("visits", { ra, dec }, signal);

// mode: epoch (one image per visit) | diff (each visit minus `ref`) | rgb (3 visits as R,G,B) | single
export async function getFrames({ ra, dec, fov, mode, ref }, signal) {
  const data = await fromApi("frames", { ra, dec, fov, mode, ref }, signal);
  const base = `${(await apiBase()) || location.origin}/`;
  data.frames = data.frames.map((f) => ({ ...f, png: new URL(f.png, base).href }));
  return data;
}

// Surface-brightness spectrum at (ra, dec), right for nebulae, reusing the open field's
// cutouts (field_ra, field_dec, fov).
export const getSpectrum = (q, signal) => fromApi("surface-spectrum", q, signal);

// Point-source spectrum (Person C): PSF photometry in mJy, with nearby stars fitted out, a
// WISE W2 cross-check and a saturation note. For catalog objects with spectrum: "point".
// See docs/SPECTRUM_API.md. `unit` is copied up so both spectra draw the same way.
export const getPointSpectrum = ({ ra, dec, target }, signal) =>
  fromApi("spectrum", { ra, dec, target }, signal).then((s) => ({ ...s, unit: s.units.flux, point: true }));

export const resolveName = (name, signal) => fromApi("resolve", { name }, signal);
