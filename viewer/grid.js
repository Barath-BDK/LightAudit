// The canonical equirectangular direction grid (BUILD_SPEC 5.2). Mirror of lightaudit/grid.py.
// Pure module: no DOM, no Three.js, so it also runs under Node for the parity test.

export const NA = 128;
export const NE = 64;
export const D = NA * NE;

const f32 = Math.fround;

/** Float64Array [D*3] of the cell directions, rounded through float32 exactly like eq_dirs() in Python. */
export const DIRS = (() => {
  const d = new Float64Array(D * 3);
  for (let j = 0; j < NE; j++) {
    const lat = Math.PI / 2 - (j + 0.5) * Math.PI / NE;
    for (let i = 0; i < NA; i++) {
      const az = -Math.PI + (i + 0.5) * 2 * Math.PI / NA;
      const k = (j * NA + i) * 3;
      d[k] = f32(Math.cos(lat) * Math.sin(az));
      d[k + 1] = f32(Math.sin(lat));
      d[k + 2] = f32(Math.cos(lat) * Math.cos(az));
    }
  }
  return d;
})();

/** Float64Array [D] solid-angle weight per cell, sums to 1. */
export const AREA = (() => {
  const w = new Float64Array(D);
  let s = 0;
  for (let j = 0; j < NE; j++) {
    const c = Math.cos(Math.PI / 2 - (j + 0.5) * Math.PI / NE);
    for (let i = 0; i < NA; i++) { w[j * NA + i] = c; }
    s += c * NA;
  }
  for (let k = 0; k < D; k++) w[k] /= s;
  return w;
})();

export function dir(k) {
  return [DIRS[3 * k], DIRS[3 * k + 1], DIRS[3 * k + 2]];
}

export function normalize(v) {
  const n = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / n, v[1] / n, v[2] / n];
}

export function dirToCell(v) {
  const d = normalize(v);
  const az = Math.atan2(d[0], d[2]);
  const lat = Math.asin(Math.max(-1, Math.min(1, d[1])));
  const i = ((Math.floor((az + Math.PI) / (2 * Math.PI) * NA) % NA) + NA) % NA;
  const j = Math.max(0, Math.min(NE - 1, Math.floor((Math.PI / 2 - lat) / Math.PI * NE)));
  return [j, i];
}

export function dirToIndex(v) {
  const [j, i] = dirToCell(v);
  return j * NA + i;
}

export function angleDeg(a, b) {
  const x = normalize(a), y = normalize(b);
  const c = Math.max(-1, Math.min(1, x[0] * y[0] + x[1] * y[1] + x[2] * y[2]));
  return Math.acos(c) * 180 / Math.PI;
}

/** Azimuth clockwise from the camera direction seen from above (atan2(x, z)), elevation asin(y), degrees. */
export function azElDeg(v) {
  const d = normalize(v);
  return [Math.atan2(d[0], d[2]) * 180 / Math.PI, Math.asin(Math.max(-1, Math.min(1, d[1]))) * 180 / Math.PI];
}

export function fromAzElDeg(az, el) {
  const a = az * Math.PI / 180, e = el * Math.PI / 180;
  return [Math.cos(e) * Math.sin(a), Math.sin(e), Math.cos(e) * Math.cos(a)];
}

/**
 * Highest-density sets of a non-negative map (stable sort, ties by cell index; searchsorted 'left').
 * Returns { fracs: [sphere fraction per level], masks: [Uint8Array per level] }.
 */
export function hpd(P, levels = [0.68, 0.95], wantMasks = false) {
  let tot = 0;
  const mass = new Float64Array(D);
  for (let k = 0; k < D; k++) { mass[k] = P[k] * AREA[k]; tot += mass[k]; }
  const order = new Uint32Array(D);
  for (let k = 0; k < D; k++) order[k] = k;
  order.sort((a, b) => (P[b] - P[a]) || (a - b));
  const den = tot > 0 ? tot : 1;
  const fracs = [], masks = [];
  for (const lv of levels) {
    const target = lv - 1e-12;
    let cum = 0, n = D;
    for (let t = 0; t < D; t++) {
      cum += mass[order[t]];
      if (cum / den >= target) { n = t + 1; break; }
    }
    let f = 0;
    for (let t = 0; t < n; t++) f += AREA[order[t]];
    fracs.push(f);
    if (wantMasks) {
      const m = new Uint8Array(D);
      for (let t = 0; t < n; t++) m[order[t]] = 1;
      masks.push(m);
    }
  }
  return { fracs, masks };
}

export function coneHalfAngleDeg(frac) {
  return Math.acos(Math.max(-1, Math.min(1, 1 - 2 * frac))) * 180 / Math.PI;
}

/** Unit vector from the surface point at pixel (u, v) toward the camera (BUILD_SPEC 5.1). */
export function viewVector(u, v, W, H, fovDeg = 60) {
  const f = (W / 2) / Math.tan(fovDeg * Math.PI / 360);
  return normalize([-(u - W / 2) / f, (v - H / 2) / f, 1]);
}

/** Pixel ray (camera centre into the scene) for pixel (u, v). */
export function pixelRay(u, v, W, H, fovDeg = 60) {
  const f = (W / 2) / Math.tan(fovDeg * Math.PI / 360);
  return normalize([(u - W / 2) / f, -(v - H / 2) / f, -1]);
}
