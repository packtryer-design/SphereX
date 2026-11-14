// View state <-> URL, so any view is a shareable link.
//   ?o=orion&tab=explore&view=blink&a=1&b=3          a catalog object
//   ?ra=83.82&dec=-5.39&fov=0.2&name=M42&tab=about   any position (from a name lookup)
export const TABS = ["explore", "observations", "spectrum", "about"];
export const VIEWS = ["sequence", "blink", "side", "swipe", "diff", "rgb"];
const KEYS = ["o", "ra", "dec", "fov", "name", "tab", "view", "v", "a", "b"];

export function readState() {
  const p = new URLSearchParams(location.search);
  const num = (k) => {
    const n = Number.parseFloat(p.get(k));
    return Number.isFinite(n) ? n : null;
  };
  const ra = num("ra"), dec = num("dec");
  return {
    objectId: p.get("o"),
    custom: ra != null && dec != null ? { ra, dec, fov: num("fov"), name: p.get("name") } : null,
    tab: TABS.includes(p.get("tab")) ? p.get("tab") : "explore",
    view: VIEWS.includes(p.get("view")) ? p.get("view") : "sequence",
    visit: num("v"), a: num("a"), b: num("b"), // epoch numbers
  };
}

// Keeps unrelated params (api, embed) intact.
export function writeState({ object, tab, view, visit, a, b }) {
  const p = new URLSearchParams(location.search);
  for (const k of KEYS) p.delete(k);
  if (object?.custom) {
    p.set("ra", object.ra); p.set("dec", object.dec); p.set("fov", object.fov); p.set("name", object.name);
  } else if (object) {
    p.set("o", object.id);
  }
  if (object) {
    p.set("tab", tab);
    p.set("view", view);
    if (view === "sequence" && visit != null) p.set("v", visit);
    if (view !== "sequence" && view !== "rgb") {
      if (a != null) p.set("a", a);
      if (b != null) p.set("b", b);
    }
  }
  const qs = p.toString();
  history.replaceState(null, "", qs ? `${location.pathname}?${qs}` : location.pathname);
}
