// Search box: instant matches from the catalog, plus a name lookup (SIMBAD/NED via the API)
// for anything else. Keyboard: arrows to move, Enter to open, Esc to close.
import { KINDS } from "./kinds.js";

const norm = (s) => String(s ?? "").toLowerCase().normalize("NFKD").replace(/[^a-z0-9]/g, "");

function score(o, q) {
  const fields = [o.name, o.simbad_id, ...(o.aliases ?? []), o.constellation, KINDS[o.kind]?.label];
  let best = 0;
  fields.forEach((f, i) => {
    const n = norm(f);
    if (!n) return;
    const weight = i === 0 ? 3 : i <= 1 + (o.aliases?.length ?? 0) ? 2 : 1; // name > catalog ids > constellation, kind
    if (n === q) best = Math.max(best, 10 * weight);
    else if (n.startsWith(q)) best = Math.max(best, 6 * weight);
    else if (n.includes(q)) best = Math.max(best, 3 * weight);
  });
  return best;
}

export function visitBadge(o) {
  const v = o.visits;
  if (!v) return { text: "", cls: "" };
  if (v.n === 0) return { text: "No SPHEREx data yet", cls: "" };
  return { text: `${v.n} visit${v.n === 1 ? "" : "s"}`, cls: "has" };
}

export function setupSearch({ input, list, getCatalog, onPick, onLookup }) {
  let items = [];
  let active = -1;

  function close() {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    active = -1;
  }

  function highlight(i) {
    active = i;
    list.querySelectorAll("li[role=option]").forEach((li, j) => li.setAttribute("aria-selected", String(j === i)));
    const li = list.querySelector(`#sr-${i}`);
    if (li) {
      input.setAttribute("aria-activedescendant", li.id);
      li.scrollIntoView({ block: "nearest" });
    }
  }

  function render() {
    const raw = input.value.trim();
    const q = norm(raw);
    if (!q) return close();
    const matches = getCatalog()
      .map((o) => ({ o, s: score(o, q) }))
      .filter((m) => m.s > 0)
      .sort((a, b) => b.s - a.s || a.o.name.localeCompare(b.o.name))
      .slice(0, 8)
      .map((m) => ({ type: "object", o: m.o }));
    items = raw.length >= 2 ? [...matches, { type: "lookup", name: raw }] : matches;

    list.replaceChildren(...items.map((it, i) => {
      const li = document.createElement("li");
      li.id = `sr-${i}`;
      li.setAttribute("role", "option");
      if (it.type === "object") {
        const badge = visitBadge(it.o);
        const aka = it.o.aliases?.find((a) => norm(a).includes(q)) ?? it.o.aliases?.[0] ?? "";
        li.innerHTML = `<span class="r-name"></span><span class="r-sub"></span><span class="badge r-badge"></span>`;
        li.querySelector(".r-name").textContent = it.o.name;
        li.querySelector(".r-sub").textContent = [KINDS[it.o.kind]?.label, aka, it.o.constellation].filter(Boolean).join(" · ");
        const b = li.querySelector(".r-badge");
        b.textContent = badge.text;
        if (badge.cls) b.classList.add(badge.cls);
        if (!badge.text) b.remove();
      } else {
        li.innerHTML = `<span class="r-name"></span><span class="r-sub">Find any object by name in SIMBAD / NED</span>`;
        li.querySelector(".r-name").textContent = `Look up “${it.name}”`;
      }
      li.addEventListener("pointerdown", (e) => { e.preventDefault(); choose(i); });
      return li;
    }));
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    highlight(items.length ? 0 : -1);
  }

  function choose(i) {
    const it = items[i];
    if (!it) return;
    close();
    input.blur();
    input.value = "";
    if (it.type === "object") onPick(it.o);
    else onLookup(it.name);
  }

  input.addEventListener("input", render);
  input.addEventListener("focus", () => { if (input.value.trim()) render(); });
  input.addEventListener("blur", () => setTimeout(close, 120));
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); if (list.hidden) render(); else highlight(Math.min(active + 1, items.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); highlight(Math.max(active - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); if (!list.hidden && active >= 0) choose(active); }
    else if (e.key === "Escape") { close(); input.blur(); }
  });
}
