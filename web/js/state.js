// View state <-> URL, so any view is a shareable link.
//   ?field=demo-field&layer=3&view=flip
// Later, with the backend: ?ra=&dec=&fov=&mode=&t= (see docs/PLAN.md).
export const VIEWS = ["flip", "stack"];

export function readState() {
  const p = new URLSearchParams(location.search);
  const layer = Number.parseInt(p.get("layer"), 10);
  return {
    field: p.get("field"), // null -> first dataset
    layer: Number.isFinite(layer) && layer >= 0 ? layer : 0,
    view: VIEWS.includes(p.get("view")) ? p.get("view") : "flip",
  };
}

// Keeps unrelated params (api, embed) intact.
export function writeState(state) {
  const p = new URLSearchParams(location.search);
  for (const k of ["field", "layer", "view"]) p.set(k, state[k]);
  history.replaceState(null, "", `${location.pathname}?${p}`);
}
