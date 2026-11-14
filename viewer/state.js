// Shared state, events, preferences and bundle loading (BUILD_SPEC 11, 12).

import { D } from './grid.js';

const listeners = new Map();
export function on(evt, fn) {
  if (!listeners.has(evt)) listeners.set(evt, new Set());
  listeners.get(evt).add(fn);
  return () => listeners.get(evt).delete(fn);
}
export function emit(evt, payload) {
  for (const fn of listeners.get(evt) || []) fn(payload);
}

/** localStorage wrapped in try/catch: it can throw or be empty (private mode, blocked storage). */
export const prefs = {
  get(key, dflt) {
    try { const v = localStorage.getItem('lightaudit.' + key); return v === null ? dflt : JSON.parse(v); } catch { return dflt; }
  },
  set(key, val) {
    try { localStorage.setItem('lightaudit.' + key, JSON.stringify(val)); } catch { /* storage unavailable */ }
  },
};

export const BUNDLES = '../bundles/';

export const state = {
  bundle: null,        // loaded bundle (see loadBundle)
  use: [],             // per region: true = used (not excluded)
  cfg: null,           // live fusion config (from manifest.calibration, editable)
  light: [0.5, 0.6, 0.6],
  selected: null,      // region index
  hover: null,
  mode: prefs.get('mode', 'observed'),
  outlines: true,
  shell: prefs.get('shell', 'selected'),
  cones: prefs.get('cones', true),
  baseline: 'rank',
  split: false,
  splitPos: 0.5,
  spec: 'off',
  heatGain: 1,
  fusion: null,        // live fusion result
  display: null,       // display shortfalls
  whatIf: null,
  pseudo: [],          // scene-level pseudo regions (shadow pairs)
  modified: false,
  api: false,
};

export async function fetchJSON(url) {
  const r = await fetch(url, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}

export async function fetchF32(url) {
  const r = await fetch(url, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return new Float32Array(await r.arrayBuffer());
}

/** Decodes an image without colour management. Returns { bitmap, data (RGBA Uint8ClampedArray), w, h }. */
export async function loadImage(url) {
  const r = await fetch(url, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  const bitmap = await createImageBitmap(await r.blob(), { colorSpaceConversion: 'none', premultiplyAlpha: 'none' });
  const c = document.createElement('canvas');
  c.width = bitmap.width; c.height = bitmap.height;
  const ctx = c.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(bitmap, 0, 0);
  return { bitmap, data: ctx.getImageData(0, 0, c.width, c.height).data, w: c.width, h: c.height, url };
}

function slices(all, n) {
  return Array.from({ length: n }, (_, k) => all.subarray(k * D, (k + 1) * D));
}

/** Loads manifest, maps and images of bundles/<name>/. Optional files are only requested when the manifest says
 *  they exist, so a missing optional file never shows up as a failed request. */
export async function loadBundle(name, onProgress = () => {}) {
  const base = `${BUNDLES}${name}/`;
  const manifest = await fetchJSON(base + 'manifest.json');
  const regs = manifest.regions;
  const missing = [];
  onProgress(0.15);
  const all = await fetchF32(base + 'landscapes.bin');
  const nMaps = all.length / D;
  const A = regs.map((r) => all.subarray(r.landscape_index * D, (r.landscape_index + 1) * D));
  const hasCues = regs.some((r) => r.cue_maps && Object.keys(r.cue_maps).length);
  const optional = async (fn, what) => { try { return await fn(); } catch (e) { missing.push(what); return null; } };
  const [cueAll, lsAll] = await Promise.all([
    hasCues ? optional(() => fetchF32(base + 'cues.bin'), 'cues.bin') : null,
    manifest.baseline_ls && manifest.baseline_ls.present ? optional(() => fetchF32(base + 'landscapes_ls.bin'), 'landscapes_ls.bin') : null,
  ]);
  onProgress(0.35);
  const names = ['image', 'labels', 'normals', 'unc', 'heat', 'counterfactual', 'valid'];
  const imgs = {};
  let done = 0;
  await Promise.all(names.map(async (n) => {
    imgs[n] = n === 'image' || n === 'labels' ? await loadImage(base + n + '.png') : await optional(() => loadImage(base + n + '.png'), n + '.png');
    onProgress(0.35 + 0.6 * (++done / names.length));
  }));
  const W = imgs.image.w, H = imgs.image.h;
  const labelToIndex = new Int16Array(256).fill(-1);
  regs.forEach((r, i) => { if (r.id < 256) labelToIndex[r.id] = i; });
  // luminance / labels on the CPU for tooltips, plots and the explain stepper
  const lab = new Uint8Array(W * H), Y = new Float32Array(W * H);
  for (let p = 0; p < W * H; p++) {
    lab[p] = imgs.labels.data[4 * p];
    const d = imgs.image.data;
    Y[p] = (0.2126 * d[4 * p] + 0.7152 * d[4 * p + 1] + 0.0722 * d[4 * p + 2]) / 255;
  }
  return {
    name, base, manifest, regions: regs, W, H, A, nMaps,
    cues: cueAll ? slices(cueAll, cueAll.length / D) : null,
    ls: lsAll ? slices(lsAll, lsAll.length / D) : null,
    images: imgs, labelToIndex, lab, Y, missing,
  };
}

/** One precomputed attack variant (bundles/<name>/attacks/<variant>/). */
export async function loadAttack(bundle, variant) {
  const base = `${bundle.base}attacks/${variant}/`;
  const manifest = await fetchJSON(base + 'manifest.json');
  const all = await fetchF32(base + 'landscapes.bin');
  const A = manifest.regions.map((r) => all.subarray(r.landscape_index * D, (r.landscape_index + 1) * D));
  const [image, heat] = await Promise.all([loadImage(base + 'image.png'), loadImage(base + 'heat.png').catch(() => null)]);
  return { variant, manifest, A, image, heat };
}

/** True when served by the LightAudit FastAPI server (python -m http.server has no API, so it is not probed). */
export async function detectApi() {
  try {
    const h = await fetch(location.href, { method: 'HEAD' });
    if ((h.headers.get('server') || '').toLowerCase().includes('simplehttp')) return false;
    const r = await fetch('/api/health', { cache: 'no-store' });
    return r.ok;
  } catch { return false; }
}
