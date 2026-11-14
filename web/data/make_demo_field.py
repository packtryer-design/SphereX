"""Generate a placeholder layer stack until the real NASA SPHEREx images are dropped in.

Stdlib only. Run from the repo root:  python web/data/make_demo_field.py
Writes web/data/demo-field/ (one SVG per wavelength + layers.json) and web/data/datasets.json.

Each layer shows the same fake field. Things in it change brightness with wavelength, so
clicking them gives different spectra:
  - stars fade toward long wavelengths
  - hydrogen gas glows in Pa-delta (1.0 um) and Pa-beta (1.3 um)
  - PAH dust glows at 3.3 um
  - a dust lane blocks short wavelengths and turns transparent at long ones
  - a cold object only appears at 3.3 and 5 um
"""

import json
import random
from pathlib import Path

DATA = Path(__file__).parent
FIELD = DATA / "demo-field"
W, H = 360, 630  # portrait, like the NASA release images

LAYERS = [
    {"wavelength_um": 0.85, "feature": None, "tint": "#4f8dff"},
    {"wavelength_um": 1.0, "feature": "Paδ", "tint": "#4fe0ff"},
    {"wavelength_um": 1.1, "feature": None, "tint": "#5cf06a"},
    {"wavelength_um": 1.3, "feature": "Paβ", "tint": "#ffe45c"},
    {"wavelength_um": 3.3, "feature": "PAH", "tint": "#ffb04a"},
    {"wavelength_um": 5.0, "feature": None, "tint": "#ff5c5c"},
]

rng = random.Random(102)
STARS = [(rng.uniform(5, W - 5), rng.uniform(5, H - 5), rng.uniform(0.5, 2.2)) for _ in range(160)]
GAS = [(170, 150, 60), (200, 470, 70)]  # hydrogen clouds (x, y, radius)
PAH = [(185, 140, 75, 18), (190, 480, 85, 20)]  # glowing rims (x, y, radius, thickness)
COLD = (260, 330)


def hex_rgb(h: str) -> tuple[int, int, int]:
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def shade(tint: str, level: float) -> str:
    """0 = black, 0.6 = full tint, 1 = white."""
    level = max(0.0, min(1.0, level))
    r, g, b = hex_rgb(tint)
    if level < 0.6:
        k = level / 0.6
        return f"rgb({r * k:.0f},{g * k:.0f},{b * k:.0f})"
    k = (level - 0.6) / 0.4
    return f"rgb({r + (255 - r) * k:.0f},{g + (255 - g) * k:.0f},{b + (255 - b) * k:.0f})"


def layer_svg(w: float, tint: str, feature: str | None) -> str:
    star = (0.85 / w) ** 1.2
    gas = 1.0 if feature in ("Paδ", "Paβ") else 0.2
    pah = 1.0 if feature == "PAH" else (0.35 if w > 4 else 0.1)
    dust = 0.75 * (0.85 / w) ** 1.5
    cold = {3.3: 0.8, 5.0: 1.0}.get(w, 0.0)
    bg = 0.18 + (0.08 if w > 4 else 0)  # zodiacal glow is stronger at 5 um

    parts = [f'<rect width="100%" height="100%" fill="{shade(tint, bg)}"/>']
    parts.append(
        "<defs><radialGradient id='g'><stop offset='0' stop-color='#fff' stop-opacity='1'/>"
        "<stop offset='1' stop-color='#fff' stop-opacity='0'/></radialGradient></defs>"
    )
    for x, y, r in GAS:
        parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="url(#g)" opacity="{0.55 * gas:.2f}"/>')
    for x, y, r, t in PAH:
        parts.append(
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="#fff" '
            f'stroke-width="{t}" stroke-opacity="{0.5 * pah:.2f}"/>'
        )
    parts.append(
        f'<path d="M-20 360 C 90 300, 220 420, 380 330 L 380 380 C 220 470, 90 350, -20 410 Z" '
        f'fill="#000" opacity="{dust:.2f}"/>'
    )
    for x, y, r in STARS:
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" fill="#fff" opacity="{min(1, 0.25 + star * r / 2):.2f}"/>')
    if cold:
        parts.append(f'<circle cx="{COLD[0]}" cy="{COLD[1]}" r="9" fill="url(#g)" opacity="{cold:.2f}"/>')
        parts.append(f'<circle cx="{COLD[0]}" cy="{COLD[1]}" r="2.5" fill="#fff" opacity="{cold:.2f}"/>')

    # Tint everything except the background by recolouring white -> tint-to-white ramp.
    body = "".join(parts).replace("#fff", shade(tint, 0.95))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
        f"{body}</svg>\n"
    )


def main() -> None:
    FIELD.mkdir(parents=True, exist_ok=True)
    layers = []
    for layer in LAYERS:
        w = layer["wavelength_um"]
        name = f"layer-{w:.2f}um.svg"
        (FIELD / name).write_text(layer_svg(w, layer["tint"], layer["feature"]), encoding="utf-8")
        layers.append({"png": name, **layer})

    manifest = {
        "id": "demo-field",
        "name": "Demo field (placeholder)",
        "credit": "Generated placeholder. Replace with NASA/JPL-Caltech SPHEREx images.",
        "layers": layers,
    }
    (FIELD / "layers.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    datasets = {"datasets": [{"id": "demo-field", "name": manifest["name"]}]}
    (DATA / "datasets.json").write_text(json.dumps(datasets, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
