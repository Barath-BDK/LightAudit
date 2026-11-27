// Attack lab (BUILD_SPEC 12.7): precomputed attack variants from the bundle, swipe comparison, the attacked
// region's light map on a dome next to the original cone, verdict and score before/after, fidelity, and the
// detection-by-tier summary from data/results/attack_summary.json. Live re-run via /api/attack when served by
// the LightAudit server.

import { openDialog, $, $$, toast } from './ui.js';
import { esc, VERDICT_META } from './text.js';
import { loadAttack, fetchJSON } from './state.js';
import { Dome } from './dome.js';

const TIERS = {
  T0: ['T0', 'Naive paste', 'The edit as made, no extra processing.'],
  T1: ['T1', 'Colour transfer', 'Matches the region\'s colour statistics to its surroundings.'],
  T3a: ['T3a', 'Physics re-shade', 'Re-shades the region under the defender\'s own light estimate.'],
  T4: ['T4', 'Adaptive', 'Re-shade + glint removal + search against the detector itself.'],
};
function tierOf(variant) {
  const t = variant.split('_')[0];
  return TIERS[t] || [t, variant, ''];
}

async function loadSummary(api) {
  // with python -m http.server, read the directory listing first so a missing file is not a failed request
  const url = '../data/results/attack_summary.json';
  try {
    if (!api) {
      const r = await fetch('../data/results/', { cache: 'no-cache' });
      if (!r.ok || !(await r.text()).includes('attack_summary.json')) return null;
    }
    return await fetchJSON(url);
  } catch { return null; }
}

function drawCompare(canvas, a, b, pos, outline) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = Math.max(1, canvas.clientWidth * dpr), h = Math.max(1, canvas.clientHeight * dpr);
  if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
  const g = canvas.getContext('2d');
  g.clearRect(0, 0, w, h);
  const s = Math.min((w - 20 * dpr) / a.width, (h - 20 * dpr) / a.height);
  const x0 = (w - a.width * s) / 2, y0 = (h - a.height * s) / 2, iw = a.width * s, ih = a.height * s;
  g.drawImage(a, x0, y0, iw, ih);
  g.save();
  g.beginPath(); g.rect(x0 + iw * pos, y0, iw * (1 - pos), ih); g.clip();
  g.drawImage(b, x0, y0, iw, ih);
  g.restore();
  if (outline) g.drawImage(outline, x0, y0, iw, ih);
  g.fillStyle = '#fff'; g.fillRect(x0 + iw * pos - dpr, y0, 2 * dpr, ih);
  g.font = `500 ${13 * dpr}px -apple-system, Geist, system-ui, sans-serif`;
  const tag = (t, x, right) => {
    const tw = g.measureText(t).width + 12 * dpr;
    g.fillStyle = 'rgba(0,0,0,.62)'; g.fillRect(right ? x - tw : x, y0 + 8 * dpr, tw, 18 * dpr);
    g.fillStyle = '#fff'; g.fillText(t, (right ? x - tw : x) + 6 * dpr, y0 + 21 * dpr);
  };
  tag('Original', x0 + 8 * dpr, false);
  tag('Attacked', x0 + iw - 8 * dpr, true);
  return { x0: x0 / dpr, iw: iw / dpr };
}

function outlineCanvas(B, id) {
  const c = document.createElement('canvas');
  c.width = B.W; c.height = B.H;
  const g = c.getContext('2d');
  const img = g.createImageData(B.W, B.H), o = img.data, lab = B.lab, W = B.W;
  for (let p = 0; p < W * B.H; p++) {
    if (lab[p] !== id) continue;
    const x = p % W, y = (p / W) | 0;
    if ((x > 0 && lab[p - 1] !== id) || (x < W - 1 && lab[p + 1] !== id) || (y > 0 && lab[p - W] !== id) || (y < B.H - 1 && lab[p + W] !== id)) {
      o[4 * p] = 245; o[4 * p + 1] = 178; o[4 * p + 2] = 61; o[4 * p + 3] = 255;
    }
  }
  g.putImageData(img, 0, 0);
  return c;
}

function heatImage(B, heat) {
  const c = document.createElement('canvas');
  c.width = B.W; c.height = B.H;
  const g = c.getContext('2d'), img = g.createImageData(B.W, B.H), o = img.data;
  const stops = [[0, 0, 4], [50, 10, 94], [120, 28, 109], [188, 55, 84], [237, 105, 37], [251, 182, 26], [252, 255, 164]];
  const im = B.images.image.data;
  for (let p = 0; p < B.W * B.H; p++) {
    const v = heat.data[4 * p] / 255;
    let col;
    if (v > 0) {
      const t = v * 6, i = Math.min(5, Math.floor(t)), f = t - i;
      col = stops[i].map((a, k) => a + (stops[i + 1][k] - a) * f);
    } else {
      const gr = (0.2126 * im[4 * p] + 0.7152 * im[4 * p + 1] + 0.0722 * im[4 * p + 2]) * 0.3;
      col = [gr, gr, gr];
    }
    o[4 * p] = col[0]; o[4 * p + 1] = col[1]; o[4 * p + 2] = col[2]; o[4 * p + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  return c;
}

const nice = (n) => (n === 'ROI' ? 'marked area' : n);
const plainTier = (a) => {
  const [, name, desc] = tierOf(a.variant);
  const paren = /\(([^)]+)\)/.exec(a.title || '');
  return { name: paren ? `${name} (${paren[1]})` : name, desc };
};
const shortTier = (a) => ({ T1: 'Colour transfer', T3a: 'Re-shade', T3b: 'Re-shade', T4: 'Adaptive' })[a.variant.split('_')[0]] || plainTier(a).name;
const verdictLine = (v) => (v === 'SUSPICIOUS' ? 'Still flagged' : v === 'CONSISTENT' ? 'Passes' : (VERDICT_META[v] || { word: v }).word);

export async function openAttackLab(ctx) {
  const { B, state } = ctx;
  const m = B.manifest;
  const attacks = m.attacks || [];
  let dome = null, cur = null, pos = 0.5, showHeat = false, compareImgs = null, outline = null;
  const d = openDialog({ title: 'Attack lab', cls: 'sheet',
    foot: `<span class="spacer"></span>${state.api ? '<button class="btn primary pill" id="atk-live">Run a new attack</button>' : '<button class="btn primary pill" data-done>Done</button>'}`,
    onClose: () => { if (dome) dome.destroy(); window.removeEventListener('resize', redraw); } });
  const done = $('[data-done]', d.el);
  if (done) done.addEventListener('click', () => d.close());
  const summaryP = loadSummary(state.api);
  const topId = state.fusion.top_region !== null && B.regions[state.fusion.top_region] ? B.regions[state.fusion.top_region].id : B.regions[0].id;
  const intro = `<div class="sheet-text"><p class="ex-lead">We attack our own verdict to see how a forger could pass.</p></div>`;
  const more = `<details class="subdisclosure" id="atk-dome-box"><summary>Light dome after the attack</summary><div class="atk-dome" id="atk-dome"></div></details>
    <details class="subdisclosure"><summary>Results across all test scenes</summary><div id="summary"></div></details>
    ${state.api ? `<details class="subdisclosure"><summary>Attack options</summary><div class="sheet-text">
      <label class="check">Attacker's light error <input type="number" id="atk-sigma" value="10" min="0" max="60" step="1" class="num-in"> degrees</label>
      <div class="progress" hidden><i style="width:100%"></i></div></div></details>` : ''}`;

  const live = $('#atk-live', d.el);
  if (live) live.addEventListener('click', () => liveRun([cur ? cur.variant.split('_')[0] : 'T3a'], cur ? cur.region_id : topId));

  if (!attacks.length) {
    d.body.innerHTML = `${intro}<div class="sheet-text"><p>No attacks have been run on this photo yet.${state.api ? ' Run a new attack to try one on the flagged area.' : ' Start the LightAudit server to run one, or open <a href="?bundle=demo_damage_fake">a demo that has them</a>.'}</p></div>${more}`;
    renderSummary(await summaryP);
    return;
  }

  let rid = attacks.some((a) => a.region_id === m.fusion.top_region) ? m.fusion.top_region : attacks[0].region_id;
  const origPer = (id) => m.fusion.per_region.find((p) => p.id === id) || {};
  d.body.innerHTML = `${intro}
    <div class="segmented atk-seg" role="tablist" aria-label="Attacks" id="atk-list"></div>
    <div class="sheet-text" id="atk-result" aria-live="polite"></div>
    <div class="sheet-visual atk-visual" id="atk-stage"><canvas id="atk-canvas" aria-label="Original against attacked photo; drag to compare"></canvas></div>
    <div class="sheet-row"><label class="check"><input type="checkbox" id="atk-heat"> Show where the shading does not fit</label><span class="faint">Drag on the photo to compare</span></div>
    <p class="faint small" id="atk-cost"></p>
    ${more}`;
  const canvas = $('#atk-canvas', d.body);

  function renderList() {
    const list = attacks.filter((a) => a.region_id === rid);
    $('#atk-list', d.body).innerHTML = list.map((a) =>
      `<button role="tab" aria-selected="${!!cur && cur.variant === a.variant}" data-v="${esc(a.variant)}">${esc(shortTier(a))}</button>`).join('');
    $$('#atk-list button', d.body).forEach((b) => b.addEventListener('click', () => pick(b.dataset.v)));
  }

  function redraw() {
    if (!compareImgs) return;
    drawCompare(canvas, showHeat ? compareImgs.heatA : compareImgs.a, showHeat ? compareImgs.heatB : compareImgs.b, pos, outline);
  }

  function updateDome() {
    if (!cur || !$('#atk-dome-box', d.body).open) return;
    if (!dome) { dome = new Dome($('#atk-dome', d.body), { draggable: false, labels: false }); dome.setPhoto(B.images.image.bitmap, B.W, B.H); dome.applyTheme(); }
    const reg = B.regions.find((r) => r.id === rid);
    const ar = cur.manifest.regions.find((r) => r.id === rid);
    dome.setShell('map', cur.A[cur.manifest.regions.indexOf(ar)]);
    const cones = [{ center: reg.center, r68: 180, r95: reg.r95_deg, color: reg.color, dashedOnly: true, dim: true }];
    if (ar && ar.r68_deg < 179) cones.push({ center: ar.center, r68: ar.r68_deg, r95: ar.r95_deg, color: reg.color, selected: true,
      flagged: (cur.manifest.fusion.flagged || []).includes(rid) });
    const c = cur.manifest.fusion.consensus;
    dome.setCones(cones, c ? { dir: c.dir, r68: c.r68_deg, r95: c.r95_deg } : null);
  }

  async function pick(variant) {
    const meta = attacks.find((a) => a.variant === variant);
    let at;
    try { at = await loadAttack(B, variant); } catch (e) { toast(`Could not load attack ${variant}: ${e.message}`, 'err'); return; }
    cur = { ...meta, ...at };
    renderList();
    const reg = B.regions.find((r) => r.id === rid);
    outline = outlineCanvas(B, rid);
    compareImgs = { a: B.images.image.bitmap, b: at.image.bitmap,
      heatA: B.images.heat ? heatImage(B, B.images.heat) : B.images.image.bitmap,
      heatB: at.heat ? heatImage(B, at.heat) : at.image.bitmap };
    redraw();
    updateDome();
    const before = origPer(rid), after = (at.manifest.fusion.per_region || []).find((p) => p.id === rid) || {};
    const n2 = (x) => (x === null || x === undefined ? 'none' : Math.max(0, x).toFixed(2));
    const a0 = (x) => (x === null || x === undefined ? 'unknown' : `${x.toFixed(0)}°`);
    const fid = meta.fidelity || {};
    const t = plainTier(meta), tau = state.cfg.tau_img;
    const whyLine = meta.verdict !== 'SUSPICIOUS' ? 'This edit would pass the lighting check.'
      : meta.S_img != null && meta.S_img < tau ? `The image score is under the alert level, but the panel test still flags the ${nice(reg.name)}.`
      : 'The image score is still over the alert level.';
    $('#atk-result', d.body).innerHTML = `
      <p class="atk-head"><span class="atk-name">${esc(t.name)}</span><span class="atk-res v-${esc(meta.verdict)}">${esc(verdictLine(meta.verdict))}</span></p>
      <p class="atk-why">${esc(whyLine)} The ${esc(nice(reg.name))} went from ${a0(before.angle_deg)} to ${a0(after.angle_deg)} off the shared light, and the image score from ${n2(m.fusion.S_img)} to ${n2(meta.S_img)} (alert level ${tau.toFixed(2)}).</p>`;
    $('#atk-cost', d.body).textContent = fid.mean_abs_dY !== undefined ? `${t.desc} Cost to the photo: brightness changed by ${fid.mean_abs_dY.toFixed(3)} on average${fid.ssim_loss !== undefined ? `, structure similarity dropped by ${fid.ssim_loss.toFixed(3)}` : ''}.` : t.desc;
  }

  async function liveRun(variants, regionId) {
    const sigma = +($('#atk-sigma', d.body)?.value || 10);
    const bar = $('.progress', d.body);
    if (bar) bar.hidden = false;
    try {
      const r = await fetch('/api/attack', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bundle: B.name, region: regionId, variants, sigma_att: sigma }) });
      if (!r.ok) throw new Error(`HTTP ${r.status} ${await r.text()}`);
      await r.json();
      const fresh = await ctx.reload();
      toast('Attack finished; the photo was reloaded.');
      d.close();
      openAttackLab({ ...ctx, B: fresh });
    } catch (e) {
      toast(`Live attack failed: ${e.message}`, 'err', 8000);
    } finally { if (bar) bar.hidden = true; }
  }

  const move = (e) => {
    const r = canvas.getBoundingClientRect();
    const info = drawCompare(canvas, showHeat ? compareImgs.heatA : compareImgs.a, showHeat ? compareImgs.heatB : compareImgs.b, pos, outline);
    pos = Math.max(0, Math.min(1, (e.clientX - r.left - info.x0) / info.iw));
    redraw();
  };
  canvas.addEventListener('pointerdown', (e) => { canvas.setPointerCapture(e.pointerId); move(e); canvas.onpointermove = move; });
  canvas.addEventListener('pointerup', () => { canvas.onpointermove = null; });
  canvas.tabIndex = 0;
  canvas.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); e.stopPropagation(); pos = Math.max(0, Math.min(1, pos + (e.key === 'ArrowLeft' ? -0.05 : 0.05))); redraw(); }
  });
  $('#atk-heat', d.body).addEventListener('change', (e) => { showHeat = e.target.checked; redraw(); });
  $('#atk-dome-box', d.body).addEventListener('toggle', updateDome);
  window.addEventListener('resize', redraw);
  new ResizeObserver(redraw).observe($('#atk-stage', d.body));
  const firstT3 = attacks.find((a) => a.region_id === rid && a.variant.startsWith('T3a')) || attacks.find((a) => a.region_id === rid);
  await pick(firstT3.variant);
  renderSummary(await summaryP);

  function renderSummary(s) {
    const el = $('#summary', d.body);
    if (!el) return;
    if (!s || !Array.isArray(s.rows) || !s.rows.length) {
      el.innerHTML = '<p class="faint">No evaluation summary yet. It is written to data/results/attack_summary.json by python -m lightaudit.cli eval.</p>';
      return;
    }
    const pct = (x) => (typeof x === 'number' ? `${(x * 100).toFixed(0)}%` : 'none');
    el.innerHTML = `<p class="faint">How often each kind of attack was still caught, across the synthetic test scenes.</p>
      <ul class="sum-list">${s.rows.map((r) => `<li><span>${esc(r.label || r.tier)}</span><span>${pct(r.tpr_fused)} caught</span></li>`).join('')}</ul>
      ${s.caveat ? `<p class="faint">${esc(s.caveat)}</p>` : ''}`;
  }
}
