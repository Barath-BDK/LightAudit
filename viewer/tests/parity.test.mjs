// JS <-> Python parity for the EQ grid and the fusion (BUILD_SPEC 12.4, 17.10).
// Run from the project root:  node viewer/tests/parity.test.mjs
// Vectors are written by pytest (tests/test_grid.py, tests/test_fusion.py) into tests/vectors/.
// Exits non-zero on any mismatch.

import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import * as grid from '../grid.js';
import { fuse, combineCues, DEFAULT_CFG } from '../fusion.js';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const VEC = join(ROOT, 'tests', 'vectors');
let failures = 0, checks = 0;

function check(cond, msg) {
  checks++;
  if (!cond) { failures++; console.error('  FAIL ' + msg); }
}
const close = (a, b, tol) => (a === null || a === undefined) ? (b === null || b === undefined) : Math.abs(a - b) <= tol;

function decodeF32(b64, R) {
  const buf = Buffer.from(b64, 'base64');
  const f = new Float32Array(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
  if (f.length !== R * grid.D) throw new Error(`A_b64 has ${f.length} floats, expected ${R * grid.D}`);
  return Array.from({ length: R }, (_, r) => f.subarray(r * grid.D, (r + 1) * grid.D));
}

// ---------------------------------------------------------------- grid
const gpath = join(VEC, 'grid_vectors.json');
if (!existsSync(gpath)) { console.error(`missing ${gpath} (run pytest tests/test_grid.py first)`); process.exit(2); }
const gv = JSON.parse(readFileSync(gpath, 'utf8'));
check(gv.NA === grid.NA && gv.NE === grid.NE, 'grid size');
for (const c of gv.cells) {
  const d = grid.dir(c.k);
  check(Math.abs(d[0] - c.dir[0]) < 1e-6 && Math.abs(d[1] - c.dir[1]) < 1e-6 && Math.abs(d[2] - c.dir[2]) < 1e-6,
    `cell ${c.k} direction ${d} vs ${c.dir}`);
  check(Math.abs(grid.AREA[c.k] - c.area) < 1e-12, `cell ${c.k} area ${grid.AREA[c.k]} vs ${c.area}`);
}
for (const c of gv.dir_to_index) check(grid.dirToIndex(c.dir) === c.k, `dirToIndex ${c.dir} -> ${grid.dirToIndex(c.dir)} vs ${c.k}`);
for (const c of gv.az_el) {
  const [az, el] = grid.azElDeg(c.dir);
  check(close(az, c.az_el[0], 1e-9) && close(el, c.az_el[1], 1e-9), `azEl ${c.dir}`);
}
let s = 0;
for (let k = 0; k < grid.D; k++) s += grid.AREA[k];
check(Math.abs(s - 1) < 1e-9, 'area weights sum to 1');
console.log(`grid: ${gv.cells.length} cells, ${gv.dir_to_index.length} lookups`);

// ---------------------------------------------------------------- fusion
const fpath = join(VEC, 'fusion_vectors.json');
if (!existsSync(fpath)) { console.error(`missing ${fpath} (run pytest tests/test_fusion.py first)`); process.exit(2); }
const fv = JSON.parse(readFileSync(fpath, 'utf8'));
const cfg = { ...DEFAULT_CFG, ...fv.cfg };
const verdicts = new Set();
fv.cases.forEach((c, n) => {
  const A = decodeF32(c.A_b64, c.R);
  const e = c.expected;
  const f = fuse(A, c.weights, c.excluded, cfg, c.centers);
  const tag = `case ${n}`;
  verdicts.add(f.verdict);
  check(f.verdict === e.verdict, `${tag}: verdict ${f.verdict} vs ${e.verdict}`);
  check(close(f.S_img, e.S_img, 1e-4), `${tag}: S_img ${f.S_img} vs ${e.S_img}`);
  check(JSON.stringify(f.flagged) === JSON.stringify(e.flagged), `${tag}: flagged ${f.flagged} vs ${e.flagged}`);
  check(f.top_region === e.top_region, `${tag}: top_region ${f.top_region} vs ${e.top_region}`);
  const ci = f.consensus ? f.consensus.index : null;
  check(ci === e.consensus_index, `${tag}: consensus index ${ci} vs ${e.consensus_index}`);
  if (f.consensus && e.r68_deg !== null) {
    check(close(f.consensus.r68_deg, e.r68_deg, 1e-3), `${tag}: r68 ${f.consensus.r68_deg} vs ${e.r68_deg}`);
    check(close(f.consensus.r95_deg, e.r95_deg, 1e-3), `${tag}: r95 ${f.consensus.r95_deg} vs ${e.r95_deg}`);
  }
  e.per_region.forEach((p, k) => {
    const q = f.per_region[k];
    check(close(q.shortfall, p.shortfall, 1e-4), `${tag} region ${k}: shortfall ${q.shortfall} vs ${p.shortfall}`);
    check(close(q.angle_deg, p.angle_deg, 1e-3), `${tag} region ${k}: angle ${q.angle_deg} vs ${p.angle_deg}`);
    check(q.ref_index === p.ref_index, `${tag} region ${k}: ref_index ${q.ref_index} vs ${p.ref_index}`);
    check(q.reliable === p.reliable && q.flagged === p.flagged, `${tag} region ${k}: reliable/flagged`);
  });
});
console.log(`fusion: ${fv.cases.length} cases, verdicts seen: ${[...verdicts].join(', ')}`);

// combine_cues sanity (max 1, identity for shading only)
{
  const A = decodeF32(fv.cases[0].A_b64, fv.cases[0].R);
  const one = combineCues(A[0]);
  check(one.every((v, k) => v === A[0][k]), 'combineCues identity with shading only');
  const two = combineCues(A[0], A[1], null, cfg);
  check(Math.abs(Math.max(...two) - 1) < 1e-6, 'combineCues max = 1');
}

// optional: every bundle's stored verdict is reproduced by the JS fusion from landscapes.bin
const idxPath = join(ROOT, 'bundles', 'index.json');
if (existsSync(idxPath)) {
  const index = JSON.parse(readFileSync(idxPath, 'utf8'));
  for (const b of index) {
    const dirB = join(ROOT, 'bundles', b.name);
    const mf = join(dirB, 'manifest.json'), lb = join(dirB, 'landscapes.bin');
    if (!existsSync(mf) || !existsSync(lb)) continue;
    const m = JSON.parse(readFileSync(mf, 'utf8'));
    const buf = readFileSync(lb);
    const all = new Float32Array(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
    const regs = m.regions;
    const A = regs.map((r) => all.subarray(r.landscape_index * grid.D, (r.landscape_index + 1) * grid.D));
    const c = m.calibration;
    const bcfg = { ...DEFAULT_CFG, tau_img: c.tau_img, tau_ref: c.tau_ref, w_min: c.w_min, eps: c.eps ?? 1e-3,
      min_reliable: c.min_reliable ?? 3, broad_consensus_frac: c.broad_consensus_frac ?? 0.35 };
    const f = fuse(A, regs.map((r) => r.weight), regs.map((r) => r.excluded), bcfg, regs.map((r) => r.center));
    check(f.verdict === m.fusion.verdict, `bundle ${b.name}: verdict ${f.verdict} vs ${m.fusion.verdict}`);
    // manifest weights are rounded to 5 decimals, so compare loosely
    check(close(f.S_img, m.fusion.S_img, 2e-3), `bundle ${b.name}: S_img ${f.S_img} vs ${m.fusion.S_img}`);
    const fl = f.flagged.map((k) => regs[k].id);
    check(JSON.stringify(fl) === JSON.stringify(m.fusion.flagged), `bundle ${b.name}: flagged ${fl} vs ${m.fusion.flagged}`);
  }
  console.log(`bundles: ${index.length} manifests re-fused`);
}

if (failures) {
  console.error(`\nPARITY FAILED: ${failures} of ${checks} checks`);
  process.exit(1);
}
console.log(`\nparity OK (${checks} checks)`);
