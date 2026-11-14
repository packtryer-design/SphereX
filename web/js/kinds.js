// Plain-language text for each kind of object, and what to expect when comparing visits.
// General descriptions of the class only: no numbers about a specific object live here.
export const KINDS = {
  emission: {
    label: "Emission nebula",
    plural: "Emission nebulae",
    about: "A cloud of gas, mostly hydrogen, lit up by hot young stars inside it. Their ultraviolet light makes the gas glow, and many of these clouds are still forming new stars. In infrared, SPHEREx sees glowing hydrogen and warm dust, and it can see through dust that hides parts of the cloud in visible light.",
    overTime: "The cloud itself is light-years across and won't visibly change between visits. Look instead for small things that do: stars that vary in brightness, young stars flickering as they grow, and asteroids crossing the field.",
  },
  planetary: {
    label: "Planetary nebula",
    plural: "Planetary nebulae",
    about: "The shell of gas thrown off by a dying Sun-like star. The hot core left behind lights up the shell. The name is historical: these have nothing to do with planets.",
    overTime: "The shell is expanding, but far too slowly to see between SPHEREx visits. Differences between visits here are almost always noise, detector coverage, or something passing through the field.",
  },
  supernova_remnant: {
    label: "Supernova remnant",
    plural: "Supernova remnants",
    about: "The expanding debris of a star that exploded as a supernova. Shock waves heat the gas they run into, and that heated gas glows.",
    overTime: "Even fast debris takes years to move a single SPHEREx pixel (6 arcseconds) at these distances, so expect no visible change between visits.",
  },
  reflection: {
    label: "Reflection nebula",
    plural: "Reflection nebulae",
    about: "A cloud of dust that shines by scattering light from nearby stars. Many sit in star-forming regions, so they often hold young stars.",
    overTime: "The dust doesn't change on these timescales, but young stars embedded in it can vary in brightness from one visit to the next.",
  },
  dark: {
    label: "Dark nebula",
    plural: "Dark nebulae",
    about: "A dense cloud of dust that blocks the light from behind it. Infrared light gets through dust more easily than visible light, so SPHEREx can see a little further into it.",
    overTime: "The cloud won't change between visits. Young stars forming inside it can vary.",
  },
  wind_bubble: {
    label: "Wind-blown bubble",
    plural: "Wind-blown bubbles",
    about: "A shell of gas swept up by the powerful wind of a massive, hot star at its centre.",
    overTime: "The shell won't visibly change between visits. The central star can vary.",
  },
  moving_star: {
    label: "Fast-moving nearby star",
    plural: "For comparison: real change",
    about: "A nearby star that moves noticeably across the sky from year to year. It isn't a nebula. It's here because its change over time is real and well known, which makes it a useful check on what genuine change looks like in SPHEREx.",
    overTime: "Its position shifts between visits. In Colour-time view it leaves a coloured trail, and in Difference view it shows as a dark and bright pair, while stars that stay still cancel out.",
  },
  brown_dwarf: {
    label: "Brown dwarf",
    plural: "Brown dwarfs",
    about: "An object too small to burn hydrogen like a star, so it slowly cools. The coldest ones have water and methane in their air, which carve deep dips into their infrared spectrum, and most of their light comes out near 4 to 5 µm, right where SPHEREx looks.",
    overTime: "Nearby brown dwarfs move across the sky by several arcseconds a year, so they can shift between visits. Use the Spectrum tab to see the molecules in their air.",
  },
  young_star: {
    label: "Young star",
    plural: "Young stars",
    about: "A star still growing, with a disk of gas and dust around it. The warm disk glows in the infrared, so the star looks brighter at long SPHEREx wavelengths than a grown-up star would.",
    overTime: "Young stars flicker as material falls onto them, so their brightness can change between visits.",
  },
  variable_star: {
    label: "Pulsating red giant",
    plural: "Variable stars",
    about: "An old, swollen star that slowly pulsates, getting brighter and fainter over months. It's very bright in the infrared, often too bright for SPHEREx's detectors.",
    overTime: "Its brightness changes a lot between visits. When it's too bright the detector saturates, and Blink leaves those frames out rather than guessing.",
  },
  unknown: {
    label: "Object",
    plural: "Other",
    about: "This object came from a name lookup, so Blink has no description for it. The facts below come straight from the catalog.",
    overTime: "Compare visits to see whether anything in the field moved or changed brightness. Check the detector coverage before trusting a difference.",
  },
};

// SIMBAD object-type codes we're likely to meet, in words.
export const SIMBAD_TYPES = {
  HII: "H II region (ionised hydrogen)",
  PN: "Planetary nebula",
  SNR: "Supernova remnant",
  RNe: "Reflection nebula",
  DNe: "Dark nebula",
  ISM: "Interstellar medium",
  OpC: "Open star cluster",
  "Cl*": "Star cluster",
  "WR*": "Wolf-Rayet star",
  Rad: "Radio source",
  "BY*": "BY Draconis variable star",
  "PM*": "High proper-motion star",
  "*": "Star",
  MoC: "Molecular cloud",
  SFR: "Star-forming region",
  GNe: "Nebula",
  Cld: "Cloud",
};

// Kind from a SIMBAD/NED type code, for objects found by name lookup.
export function kindFromType(type) {
  const t = String(type ?? "");
  if (t === "HII" || t === "GNe" || t === "SFR") return "emission";
  if (t === "PN") return "planetary";
  if (t === "SNR") return "supernova_remnant";
  if (t === "RNe") return "reflection";
  if (t === "DNe") return "dark";
  if (t === "BD*") return "brown_dwarf";
  if (t === "Mi*" || t === "LP*") return "variable_star";
  if (t === "TT*" || t === "Or*" || t === "Y*O") return "young_star";
  return "unknown";
}

// The six SPHEREx detectors and the wavelengths each covers (µm).
export const DETECTORS = {
  1: [0.75, 1.09], 2: [1.10, 1.62], 3: [1.63, 2.41], 4: [2.42, 3.82], 5: [3.83, 4.41], 6: [4.42, 5.0],
};

export function detectorText(dets) {
  if (!dets?.length) return "unknown detectors";
  if (dets.length === 6) return "all 6 detectors";
  return `detector${dets.length > 1 ? "s" : ""} ${dets.join(", ")}`;
}

export function wavelengthText(dets) {
  if (!dets?.length) return "";
  return dets.map((d) => `${DETECTORS[d][0]}–${DETECTORS[d][1]} µm`).join(", ");
}
