// Read pixel brightness at one spot in every layer: a spectrum without a backend.
// Values come from display images, so they are relative brightness, not calibrated flux.
const canvases = new Map();

function pixels(src) {
  if (!canvases.has(src)) {
    canvases.set(src, (async () => {
      const img = new Image();
      img.crossOrigin = "anonymous"; // needed if images are ever served from another host
      img.src = src;
      await img.decode();
      const canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      ctx.drawImage(img, 0, 0);
      return ctx;
    })());
  }
  return canvases.get(src);
}

// fx, fy are 0..1 across the image. Averages a small box to smooth out noise.
export async function sampleLayers(layers, fx, fy, radius = 3) {
  return Promise.all(layers.map(async (layer) => {
    const ctx = await pixels(layer.png);
    const { width, height } = ctx.canvas;
    const x0 = Math.max(0, Math.round(fx * width) - radius);
    const y0 = Math.max(0, Math.round(fy * height) - radius);
    const w = Math.min(width - x0, radius * 2 + 1);
    const h = Math.min(height - y0, radius * 2 + 1);
    const { data } = ctx.getImageData(x0, y0, w, h);

    const values = [];
    for (let i = 0; i < data.length; i += 4) {
      values.push((0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2]) / 255);
    }
    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    const sd = Math.sqrt(values.reduce((a, v) => a + (v - mean) ** 2, 0) / values.length);
    return { wavelength_um: layer.wavelength_um, flux: mean, err: sd / Math.sqrt(values.length), tint: layer.tint };
  }));
}
