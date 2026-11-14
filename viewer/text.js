// Rule-based explanation sentences, generated only from the numbers (BUILD_SPEC 7.14). Mirror of
// lightaudit/explain_text.py, plus the triage wording used across the viewer. No DOM.

export const CUE_NAMES = { shading: 'shading', glint: 'specular highlight', contour: 'silhouette', shadow: 'shadow pairs', panel: 'panel comparison' };
export const REVIEW = 'A flag means "send for human review", never "this is fraud".';

export const VERDICT_META = {
  CONSISTENT: { word: 'Consistent', action: 'One light explains every reliable region. Normal processing.' },
  SUSPICIOUS: { word: 'Suspicious', action: 'Send for human review: a region disagrees with the scene light.' },
  INSUFFICIENT: { word: 'Insufficient evidence', action: 'Not enough usable lighting cues. Request a better photo.' },
  CONFLICT: { word: 'Conflict', action: 'Reference regions disagree among themselves. No automatic decision; human review.' },
};

export const REASONS = {
  f_size: 'too few usable pixels',
  f_spread: 'surface too flat',
  f_sharp: 'light direction poorly constrained',
  f_dir: 'weak directional shading (overcast/soft light?)',
  f_norm: 'normals unreliable',
};

/** Reason text for an unreliable region: the manifest reason, else the smallest reliability factor. */
export function reasonOf(region) {
  if (region.reason) return region.reason;
  const f = region.factors;
  if (!f) return 'not assessed';
  let best = null;
  for (const k of Object.keys(f)) if (best === null || f[k] < f[best]) best = k;
  return REASONS[best] || 'low reliability';
}

const r0 = (x) => Math.round(x).toString();
const f1 = (x) => x.toFixed(1);
const f2 = (x) => x.toFixed(2);

/** fusion: result of fusion.fuse(); regions[i] = { name, cues, reason }; same order as fusion.per_region. */
export function explain(fusion, regions, eps = 1e-3) {
  const v = fusion.verdict, per = fusion.per_region;
  const rel = per.filter((p) => p.reliable);
  if (v === 'CONSISTENT') {
    const c = fusion.consensus;
    const top = per[fusion.top_region];
    return `${rel.length} regions agree on one light direction (about ${r0(c.az_deg)}° azimuth, ${r0(c.el_deg)}° elevation). `
      + `The largest disagreement is ${regions[top.index].name} at ${r0(top.angle_deg ?? 0)}° (below the alert level).`;
  }
  if (v === 'SUSPICIOUS') {
    const out = fusion.flagged.map((k) => {
      const p = per[k], r = regions[k];
      if ((fusion.panel_flagged || []).includes(k)) {
        return `The brightness of **${r.name}** does not follow the shading of the panel around it `
          + `(panel score ${f1(p.panel_z)} > alert ${f1(fusion.tau_panel)}): it looks lit differently from its surroundings.`;
      }
      const agree = Math.exp(-p.shortfall) - eps;
      const cues = r.cues.map((c) => CUE_NAMES[c] || c).join(', ');
      return `The estimate for **${r.name}** points ${r0(p.angle_deg ?? 0)}° away from where `
        + `${rel.length - fusion.flagged.length} other regions agree. Its own light map does not overlap `
        + `the consensus (agreement ${f2(Math.max(agree, 0))}; shortfall ${f1(p.shortfall)} > alert `
        + `${f1(fusion.tau)}). Cues: ${cues}.`;
    });
    return out.join(' ') + ' Please review manually. ' + REVIEW;
  }
  if (v === 'INSUFFICIENT') {
    const counts = new Map();
    per.forEach((p, i) => {
      const r = regions[i];
      if (!p.reliable && !p.excluded && r.reason) counts.set(r.reason, (counts.get(r.reason) || 0) + 1);
    });
    const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1]);
    let why = sorted.map(([k, n]) => `${n} region(s): ${k}`).join('; ') || fusion.reason;
    if (sorted.length && fusion.reason) why = `${fusion.reason} (${why})`;
    return `Not enough usable lighting evidence: ${why}. Try a photo outdoors in direct light with several objects visible.`;
  }
  return 'The reference regions disagree among themselves, which usually means several lights or unreliable '
    + 'geometry. No automatic decision.';
}

/** One line for the "what-if at your light" readout. */
export function whatIfText(w, regions) {
  if (w.verdict === 'INSUFFICIENT') return `only ${w.n_reliable} reliable region(s); no what-if verdict`;
  if (w.n_flagged === 0) return `all ${w.n_reliable} reliable regions accept this light`;
  const names = w.per_region.filter((p) => p.flagged).map((p) => regions[p.index].name);
  return `${w.n_flagged} of ${w.n_reliable} reliable regions reject this light (${names.join(', ')})`;
}

export function fmtAzEl([az, el]) {
  return `az ${az.toFixed(1)}°, el ${el.toFixed(1)}°`;
}

/** Escapes text and turns **x** into <strong>x</strong>. */
export function richText(s) {
  const esc = s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return esc.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}

export function esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
