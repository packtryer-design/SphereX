// The only file that knows where data comes from.
//   data/objects.json   the searchable catalog (built from SIMBAD + IRSA by scripts/build_objects.py)
//   /api/...            the Python API, when one is running (make serve, Docker, or ?api=URL)
//   snapshot/...        otherwise: pre-built results for the demo objects, as static files
//                       (scripts/build_snapshot.py). This is what the Netlify site uses.

const OVERRIDE = (new URLSearchParams(location.search).get("api") ?? "").replace(/\/$/, "");

export class OfflineError extends Error {}
// The site is running from its snapshot and this object/view wasn't included in it.
export class NotInDemoError extends Error {}

async function getJSON(url, signal) {
  let res;
  try {
    res = await fetch(url, { signal });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new OfflineError("SpotX's data server can't be reached.");
  }
  const isJSON = (res.headers.get("content-type") ?? "").includes("json");
  if (!isJSON) throw new OfflineError("SpotX's data server isn't answering.");
  const body = await res.json();
  if (!res.ok) {
    const err = new Error(typeof body.detail === "string" ? body.detail : `${res.status} ${res.statusText}`);
    err.status = res.status;
    throw err;
  }
  return body;
}

async function liveApi(base) {
  try {
    const res = await fetch(`${base}/api/health`, { cache: "no-store", signal: AbortSignal.timeout(5000) });
    return res.ok && (res.headers.get("content-type") ?? "").includes("json");
  } catch {
    return false;
  }
}

// { kind: "api", base } or { kind: "snapshot", index }. Decided once per page load.
let sourcePromise = null;
export function dataSource() {
  sourcePromise ??= (async () => {
    if (OVERRIDE) return { kind: "api", base: OVERRIDE };
    if (await liveApi("")) return { kind: "api", base: "" };
    try {
      return { kind: "snapshot", index: await getJSON("snapshot/index.json") };
    } catch {
      throw new OfflineError("SpotX's data isn't available here.");
    }
  })();
  return sourcePromise;
}

// Catalog ids included in the snapshot, or null when a live API serves everything.
export async function snapshotIds() {
  const src = await dataSource().catch(() => null);
  return src?.kind === "snapshot" ? new Set(Object.keys(src.index.objects)) : null;
}

// ---------- snapshot lookups ----------

const near = (a, b) => Math.abs(a - b) < 2e-4;

function snapshotEntry(index, { ra, dec }) {
  const hit = Object.entries(index.objects).find(([, o]) => near(o.ra, ra) && near(o.dec, dec));
  if (!hit) throw new NotInDemoError("This object isn't in the demo.");
  return { id: hit[0], ...hit[1] };
}

async function snapshotFile(entry, key, what) {
  const file = entry.files[key];
  if (!file) throw new NotInDemoError(`${what} isn't in the demo for this object.`);
  return getJSON(`snapshot/${entry.id}/${file}`);
}

// ---------- the API, or the snapshot ----------

async function fromApi(path, query, signal) {
  const q = Object.fromEntries(Object.entries(query).filter(([, v]) => v != null));
  const { base } = await dataSource();
  return getJSON(`${base}/api/${path}?${new URLSearchParams(q)}`, signal);
}

// Turn an image path from either source into a full URL.
export async function apiUrl(path) {
  const src = await dataSource();
  if (!path || !path.startsWith("/")) return path ? new URL(path, location.href).href : path;
  return new URL(path, `${(src.kind === "api" && src.base) || location.origin}/`).href;
}

export const getCatalog = () => getJSON("data/objects.json").then((d) => d.objects);
export const getFeatures = () => getJSON("data/features.json");

// Real SPHEREx visit dates for a position.
export async function getVisits({ ra, dec }, signal) {
  const src = await dataSource();
  if (src.kind === "api") return fromApi("visits", { ra, dec }, signal);
  return snapshotFile(snapshotEntry(src.index, { ra, dec }), "visits", "The visit list");
}

// mode: epoch (one image per visit) | diff (each visit minus `ref`) | rgb (3 visits as R,G,B)
export async function getFrames({ ra, dec, fov, mode, ref }, signal) {
  const src = await dataSource();
  const data = src.kind === "api"
    ? await fromApi("frames", { ra, dec, fov, mode, ref }, signal)
    : await snapshotFile(
        snapshotEntry(src.index, { ra, dec }),
        mode === "diff" ? `diff${ref ?? 1}` : mode,
        mode === "diff" ? "This difference" : "These images",
      );
  data.frames = await Promise.all(data.frames.map(async (f) => ({ ...f, png: await apiUrl(f.png) })));
  return data;
}

// Surface-brightness spectrum at (ra, dec), right for nebulae, reusing the open field's
// cutouts (field_ra, field_dec, fov). The snapshot has it at the field centre only.
export async function getSpectrum(q, signal) {
  const src = await dataSource();
  if (src.kind === "api") return fromApi("surface-spectrum", q, signal);
  if (!near(q.ra, q.field_ra) || !near(q.dec, q.field_dec)) {
    throw new NotInDemoError("The demo has the spectrum at the centre of the field. Spectra anywhere else need SpotX's live server.");
  }
  return snapshotFile(snapshotEntry(src.index, { ra: q.field_ra, dec: q.field_dec }), "spectrum", "The spectrum");
}

// Point-source spectrum (Person C): PSF photometry in mJy, with nearby stars fitted out, a
// WISE W2 cross-check and a saturation note. For catalog objects with spectrum: "point".
// See docs/SPECTRUM_API.md. `unit` is copied up so both spectra draw the same way.
export async function getPointSpectrum({ ra, dec, target }, signal) {
  const src = await dataSource();
  let s;
  if (src.kind === "api") s = await fromApi("spectrum", { ra, dec, target }, signal);
  else if (!target) throw new NotInDemoError("The demo has the spectrum of the object itself. Spectra of other spots need SpotX's live server.");
  else s = await snapshotFile(snapshotEntry(src.index, { ra, dec }), "spectrum", "The spectrum");
  return { ...s, unit: s.units.flux, point: true };
}

export async function resolveName(name, signal) {
  const src = await dataSource();
  if (src.kind === "api") return fromApi("resolve", { name }, signal);
  throw new NotInDemoError("Looking up new objects by name needs SpotX's live server. The demo covers the objects listed on the home page.");
}

// The Planet X page (track.html): Pluto tracked through SPHEREx frames, and the planet search.
export async function getPage(name, query) {
  const src = await dataSource();
  if (src.kind === "api") return fromApi(name, query);
  const file = src.index.pages?.[name];
  if (!file) throw new NotInDemoError("This part isn't in the demo.");
  return getJSON(file);
}
