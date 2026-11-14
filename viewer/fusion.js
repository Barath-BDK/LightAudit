// Fusion, consensus, leave-one-out shortfall and verdict (BUILD_SPEC 7.11). Mirror of lightaudit/fusion.py.
// Pure module (no DOM / Three.js) so viewer/tests/parity.test.mjs can import it under Node.
//
// Parity rules taken from fusion.py: float64 arithmetic on float32 inputs; argmax = first maximum;
// the leave-one-out objective is F_total - L_k; HPD sorts are stable (ties by cell index).
// Verdict step 3 follows fusion.py (not the spec prose): candidates = {s_k > tau}; if the remaining reliable
// regions (>= 2) are mutually consistent -> SUSPICIOUS(candidates); otherwise try each candidate alone, highest
// shortfall first, and flag the first whose removal leaves a consistent rest; else CONFLICT.

import { D, DIRS, angleDeg, azElDeg, coneHalfAngleDeg, dir, hpd } from './grid.js';

export const VERDICTS = ['CONSISTENT', 'SUSPICIOUS', 'INSUFFICIENT', 'CONFLICT'];

export const DEFAULT_CFG = Object.freeze({
  eps: 1e-3, w_glint: 0.5, w_contour: 0.5, w_shadow: 0.7, w_min: 0.35, tau_img: 2.0, tau_ref: 2.0,
  min_reliable: 3, broad_consensus_frac: 0.35,
});

function argmax(a) {
  let j = 0, m = -Infinity;
  for (let k = 0; k < a.length; k++) if (a[k] > m) { m = a[k]; j = k; }
  return j;
}

/** ln A = ln(eps+P) + w_g ln(eps+glint) + w_c ln(eps+contour), then max A = 1. Returns Float32Array. */
export function combineCues(P, glint = null, contour = null, cfg = DEFAULT_CFG) {
  if (!glint && !contour) return Float32Array.from(P);
  const ln = new Float64Array(D);
  let mx = -Infinity;
  for (let k = 0; k < D; k++) {
    let v = Math.log(cfg.eps + P[k]);
    if (glint) v += cfg.w_glint * Math.log(cfg.eps + glint[k]);
    if (contour) v += cfg.w_contour * Math.log(cfg.eps + contour[k]);
    ln[k] = v;
    if (v > mx) mx = v;
  }
  const out = new Float32Array(D);
  for (let k = 0; k < D; k++) out[k] = Math.exp(ln[k] - mx);
  return out;
}

/** Precomputes ln(eps + A_k) for every region (Float64Array each). Cache it while the maps do not change. */
export function logMaps(A, eps = DEFAULT_CFG.eps) {
  return A.map((a) => {
    const l = new Float64Array(D);
    for (let k = 0; k < D; k++) l[k] = Math.log(eps + a[k]);
    return l;
  });
}

function sumRows(L, idx) {
  const F = new Float64Array(D);
  for (const k of idx) { const r = L[k]; for (let c = 0; c < D; c++) F[c] += r[c]; }
  return F;
}

function looShortfalls(lnA, L, idx, loo = true) {
  const F = sumRows(L, idx);
  const out = new Map();
  const tmp = new Float64Array(D);
  for (const k of idx) {
    let j;
    if (loo && idx.length > 1) {
      const r = L[k];
      for (let c = 0; c < D; c++) tmp[c] = F[c] - r[c];
      j = argmax(tmp);
    } else {
      j = argmax(F);
    }
    out.set(k, [-lnA[k][j], j]);
  }
  return out;
}

/**
 * A: array of R maps (Float32Array D, max 1); weights: R numbers; excluded: R booleans (or null);
 * centers: R unit vectors (or null). Options: { lnA } to pass precomputed logMaps(A), { loo }.
 * Returns the same structure as fusion.fuse() in Python (indices are 0-based region positions).
 */
export function fuse(A, weights, excluded = null, cfg = DEFAULT_CFG, centers = null, opts = {}) {
  const R = weights.length;
  const loo = opts.loo !== false;
  const w = Float64Array.from(weights);
  const excl = excluded ? excluded.map(Boolean) : new Array(R).fill(false);
  const reliable = Array.from({ length: R }, (_, k) => w[k] >= cfg.w_min && !excl[k]);
  const idx = [];
  for (let k = 0; k < R; k++) if (reliable[k]) idx.push(k);
  const lnA = opts.lnA || logMaps(A, cfg.eps);
  const L = lnA.map((l, k) => {
    const o = new Float64Array(D);
    for (let c = 0; c < D; c++) o[c] = w[k] * l[c];
    return o;
  });
  const tau = cfg.tau_img, tauRef = cfg.tau_ref;
  const per = Array.from({ length: R }, (_, k) => ({
    index: k, shortfall: null, angle_deg: null, flagged: false, reliable: reliable[k], excluded: excl[k], ref_index: null,
  }));
  const res = {
    verdict: 'INSUFFICIENT', reason: 'no reliable regions', S_img: 0, top_region: null, consensus: null,
    consensus_map: null, per_region: per, n_reliable: idx.length, flagged: [], tau,
  };
  if (idx.length === 0) return res;

  const F = sumRows(L, idx);
  const jStar = argmax(F);
  let Fmax = -Infinity;
  for (let c = 0; c < D; c++) if (F[c] > Fmax) Fmax = F[c];
  let wsum = 0;
  for (const k of idx) wsum += w[k];
  const C = new Float64Array(D), Pprod = new Float64Array(D);
  for (let c = 0; c < D; c++) { C[c] = Math.exp((F[c] - Fmax) / wsum); Pprod[c] = Math.exp(F[c] - Fmax); }
  const { fracs: [f68, f95] } = hpd(C);
  const { fracs: [broad] } = hpd(Pprod, [0.95]);
  const dStar = dir(jStar);
  const [az, el] = azElDeg(dStar);
  res.consensus = {
    dir: dStar, index: jStar, az_deg: az, el_deg: el,
    r68_deg: coneHalfAngleDeg(f68), r95_deg: coneHalfAngleDeg(f95), frac95: broad,
  };
  res.consensus_map = Float32Array.from(C);

  const sf = looShortfalls(lnA, L, idx, loo);
  for (let k = 0; k < R; k++) {
    if (excl[k]) continue;
    const [s, j] = sf.has(k) ? sf.get(k) : [-lnA[k][jStar], jStar];
    per[k].shortfall = s;
    per[k].ref_index = j;
    per[k].angle_deg = centers ? angleDeg(centers[k], dir(j)) : null;
  }
  let kTop = null, sTop = -Infinity;
  for (const [k, [s]] of sf) if (s > sTop) { sTop = s; kTop = k; }
  res.S_img = sTop;
  res.top_region = kTop;

  if (idx.length < cfg.min_reliable) {
    res.reason = `only ${idx.length} reliable region(s); at least ${cfg.min_reliable} are needed`;
    return res;
  }
  if (broad > cfg.broad_consensus_frac) {
    res.reason = 'the regions together do not pin down a light direction (consensus too broad)';
    return res;
  }
  if (res.S_img <= tau) {
    res.verdict = 'CONSISTENT';
    res.reason = '';
    return res;
  }
  const consistent = (rest) => {
    if (rest.length < 2) return false;
    let m = -Infinity;
    for (const [s] of looShortfalls(lnA, L, rest, loo).values()) if (s > m) m = s;
    return m <= tauRef;
  };
  // Python: sorted((k for k in sf if s>tau), key=-s) -- stable over dict insertion order (= idx order)
  const cand = idx.filter((k) => sf.get(k)[0] > tau).sort((a, b) => sf.get(b)[0] - sf.get(a)[0]);
  let flagged = null;
  if (consistent(idx.filter((k) => !cand.includes(k)))) {
    flagged = cand;
  } else {
    for (const k of cand) {
      if (consistent(idx.filter((x) => x !== k))) { flagged = [k]; break; }
    }
  }
  if (flagged === null) {
    res.verdict = 'CONFLICT';
    res.reason = 'reference regions disagree: several lights or poor geometry';
    return res;
  }
  for (const k of flagged) per[k].flagged = true;
  res.verdict = 'SUSPICIOUS';
  res.reason = '';
  res.flagged = flagged.slice();
  res.top_region = flagged[0];
  return res;
}

/**
 * "What-if" at the user's light (BUILD_SPEC 12.4): each region's agreement A_k(l_user) and its shortfall
 * against l_user; a reliable region is flagged when that shortfall exceeds tau. Does not change the audit.
 */
export function whatIf(A, weights, excluded, lUser, cfg = DEFAULT_CFG) {
  const R = weights.length;
  // bilinear lookup on the grid would hide the grid's discreteness; use the containing cell like the fusion
  const k = cellOf(lUser);
  const per = [];
  let nRel = 0, nFlag = 0, sMax = 0, top = null;
  for (let r = 0; r < R; r++) {
    const rel = weights[r] >= cfg.w_min && !(excluded && excluded[r]);
    const a = A[r][k];
    const s = -Math.log(cfg.eps + a);
    const flagged = rel && s > cfg.tau_img;
    if (rel) { nRel++; if (top === null || s > sMax) { sMax = s; top = r; } }
    if (flagged) nFlag++;
    per.push({ index: r, agreement: a, shortfall: s, reliable: rel, flagged });
  }
  let verdict;
  if (nRel < cfg.min_reliable) verdict = 'INSUFFICIENT';
  else verdict = nFlag === 0 ? 'CONSISTENT' : 'SUSPICIOUS';
  return { verdict, per_region: per, n_reliable: nRel, n_flagged: nFlag, S_max: sMax, top_region: top, cell: k };
}

function cellOf(v) {
  // nearest cell by dot product would cost D*3 ops; the analytic cell lookup is identical on this grid
  const n = Math.hypot(v[0], v[1], v[2]) || 1;
  const az = Math.atan2(v[0] / n, v[2] / n);
  const lat = Math.asin(Math.max(-1, Math.min(1, v[1] / n)));
  const i = ((Math.floor((az + Math.PI) / (2 * Math.PI) * 128) % 128) + 128) % 128;
  const j = Math.max(0, Math.min(63, Math.floor((Math.PI / 2 - lat) / Math.PI * 64)));
  return j * 128 + i;
}

/**
 * Shortfalls for display. For SUSPICIOUS, the non-flagged reliable regions are scored by leave-one-out within the
 * reference set (flagged regions removed), which is what verdict step 3 tested; everything else is fuse()'s value.
 * Returns per region { shortfall, angle_deg, ref_index, ref (bool: measured within the reference set) }.
 */
export function displayShortfalls(res, A, weights, cfg = DEFAULT_CFG, centers = null, lnA = null) {
  const out = res.per_region.map((p) => ({ shortfall: p.shortfall, angle_deg: p.angle_deg, ref_index: p.ref_index, ref: false }));
  if (res.verdict !== 'SUSPICIOUS') return out;
  const rest = res.per_region.filter((p) => p.reliable && !p.flagged).map((p) => p.index);
  if (rest.length < 2) return out;
  lnA = lnA || logMaps(A, cfg.eps);
  const L = lnA.map((l, k) => { const o = new Float64Array(D); for (let c = 0; c < D; c++) o[c] = weights[k] * l[c]; return o; });
  for (const [k, [s, j]] of looShortfalls(lnA, L, rest, true)) {
    out[k] = { shortfall: s, ref_index: j, ref: true, angle_deg: centers ? angleDeg(centers[k], dir(j)) : null };
  }
  return out;
}

/** Index of the maximum of a map and its direction (used for pseudo-region centres). */
export function mapArgmax(a) {
  const k = argmax(a);
  return { index: k, dir: dir(k) };
}

export { DIRS };
