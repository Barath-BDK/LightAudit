// Attack lab (BUILD_SPEC 12.7): precomputed attack variants from the bundle, swipe comparison, the attacked
// region's light map on a dome next to the original cone, verdict and score before/after, fidelity, and the
// detection-by-tier summary from data/results/attack_summary.json. Live re-run via /api/attack when served by
// the LightAudit server.

import { openDialog, chip, ICONS, $, $$, toast } from './ui.js';
import { esc, REVIEW } from './text.js';
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
  g.font = `600 ${10.5 * dpr}px system-ui, sans-serif`;
  const tag = (t, x, right) => {
    const tw = g.measureText(t).width + 12 * dpr;
    g.fillStyle = 'rgba(0,0,0,.62)'; g.fillRect(right ? x - tw : x, y0 + 8 * dpr, tw, 18 * dpr);
    g.fillStyle = '#fff'; g.fillText(t, (right ? x - tw : x) + 6 * dpr, y0 + 21 * dpr);
  };
  tag('ORIGINAL', x0 + 8 * dpr, false);
  tag('ATTACKED', x0 + iw - 8 * dpr, true);
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
      o[4 * p] = 255; o[4 * p + 1] = 138; o[4 * p + 2] = 61; o[4 * p + 3] = 255;
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

export async function openAttackLab(ctx) {
  const { B, state } = ctx;
  const m = B.manifest;
  const attacks = m.attacks || [];
  const d = openDialog({ title: 'Attack lab: can a forger make the flagged region pass?',
    onClose: () => { if (dome) dome.destroy(); window.removeEventListener('resize', redraw); } });
  let dome = null, cur = null, pos = 0.5, showHeat = false, compareImgs = null, outline = null;
  const summaryP = loadSummary(state.api);

  if (!attacks.length) {
    d.body.innerHTML = `<div class="empty"><h3>No precomputed attacks for this bundle</h3>
      <p>Attack variants are built for the spliced demos (for example <a href="?bundle=demo_splice_car">demo_splice_car</a> and <a href="?bundle=demo_damage_fake">demo_damage_fake</a>), or with <span class="mono">python -m lightaudit.cli attack --bundle ${esc(B.name)} --region ID</span>.</p>
      ${state.api ? '<p><button class="btn accent" id="live-first">Run attacks on the top region now</button></p>' : ''}</div><div id="summary"></div>`;
    const lf = $('#live-first', d.body);
    if (lf) lf.addEventListener('click', () => liveRun(['T1', 'T3a', 'T4'], state.fusion.top_region !== null ? B.regions[state.fusion.top_region].id : B.regions[0].id));
    renderSummary(await summaryP);
    return;
  }

  const regionIds = [...new Set(attacks.map((a) => a.region_id))];
  let rid = regionIds.includes(m.fusion.top_region) ? m.fusion.top_region : regionIds[0];
  const k0 = B.regions.findIndex((r) => r.id === rid);
  const origPer = (id) => m.fusion.per_region.find((p) => p.id === id) || {};

  d.body.innerHTML = `<div class="attack-grid">
    <aside class="attack-side">
      <label class="micro" for="atk-region">Target region</label>
      <select class="sel" id="atk-region">${regionIds.map((id) => `<option value="${id}">${esc(B.regions.find((r) => r.id === id)?.name || id)}</option>`).join('')}</select>
      <span class="micro" style="margin-top:6px">Attack ladder</span>
      <div class="ladder-line" role="radiogroup" aria-label="Attack variant" id="atk-list"></div>
      ${state.api ? `<div style="display:grid;gap:6px;margin-top:6px"><span class="micro">Live (server)</span>
        <label class="check">attacker light error σ <input type="number" id="atk-sigma" value="10" min="0" max="60" step="1" style="width:56px;height:24px;border:1px solid var(--line-2);border-radius:4px;background:var(--bg-2);padding:0 4px">°</label>
        <button class="btn sm" id="atk-live" title="POST /api/attack and reload this bundle">Re-run attack</button><div class="progress" hidden><i style="width:100%"></i></div></div>` : ''}
    </aside>
    <div class="compare"><div class="stage" id="atk-stage"><canvas id="atk-canvas" aria-label="Original versus attacked image; drag to compare"></canvas></div>
      <div class="panel-foot"><label class="check"><input type="checkbox" id="atk-heat"> Show residual heat maps</label><span class="spacer"></span><span class="faint">drag on the image to swipe</span></div></div>
    <div class="attack-dome"><div class="panel-head"><span class="micro">Light dome</span><span class="spacer"></span><span class="faint" style="font-size:11px">dashed = original estimate · solid + map = after attack</span></div>
      <div class="stage" id="atk-dome"></div></div>
  </div>
  <div class="metrics" id="atk-metrics"></div>
  <div class="interp" id="atk-interp"></div>
  <div class="summary-wrap" id="summary"></div>`;

  dome = new Dome($('#atk-dome', d.body), { draggable: false, labels: false });
  dome.setPhoto(B.images.image.bitmap, B.W, B.H);
  dome.applyTheme();
  const canvas = $('#atk-canvas', d.body);

  function renderList() {
    const list = attacks.filter((a) => a.region_id === rid);
    $('#atk-list', d.body).innerHTML = list.map((a) => {
      const [t, name, desc] = tierOf(a.variant);
      return `<button class="variant" role="radio" aria-checked="${cur && cur.variant === a.variant}" data-v="${esc(a.variant)}">
        <span class="tier">${esc(t)}</span><span class="vt">${esc(a.title || name)}</span><span class="vd">${esc(desc)}</span>
        <span class="vr">${chip(a.verdict, true)}</span></button>`;
    }).join('');
    $$('.variant', d.body).forEach((b) => b.addEventListener('click', () => pick(b.dataset.v)));
    $('#atk-list', d.body).onkeydown = (e) => {
      if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
      e.preventDefault();
      const i = list.findIndex((a) => a.variant === cur?.variant) + (e.key === 'ArrowDown' ? 1 : -1);
      const a = list[(i + list.length) % list.length];
      pick(a.variant).then(() => $(`.variant[data-v="${a.variant}"]`, d.body).focus());
    };
  }

  function redraw() {
    if (!compareImgs) return;
    drawCompare(canvas, showHeat ? compareImgs.heatA : compareImgs.a, showHeat ? compareImgs.heatB : compareImgs.b, pos, outline);
  }

  async function pick(variant) {
    const meta = attacks.find((a) => a.variant === variant);
    let at;
    try { at = await loadAttack(B, variant); } catch (e) { toast(`Could not load attack ${variant}: ${e.message}`, 'err'); return; }
    cur = { ...meta, ...at };
    renderList();
    const k = B.regions.findIndex((r) => r.id === rid);
    const reg = B.regions[k];
    outline = outlineCanvas(B, rid);
    compareImgs = { a: B.images.image.bitmap, b: at.image.bitmap,
      heatA: B.images.heat ? heatImage(B, B.images.heat) : B.images.image.bitmap,
      heatB: at.heat ? heatImage(B, at.heat) : at.image.bitmap };
    redraw();
    // dome: attacked region's map + cone, original cone dashed, attacked audit's consensus
    const ar = at.manifest.regions.find((r) => r.id === rid);
    const ai = at.manifest.regions.indexOf(ar);
    dome.setShell('map', at.A[ai]);
    const cones = [{ center: reg.center, r68: 180, r95: reg.r95_deg, color: reg.color, dashedOnly: true, dim: true }];
    if (ar && ar.r68_deg < 179) cones.push({ center: ar.center, r68: ar.r68_deg, r95: ar.r95_deg, color: reg.color, selected: true,
      flagged: (at.manifest.fusion.flagged || []).includes(rid) });
    const c = at.manifest.fusion.consensus;
    dome.setCones(cones, c ? { dir: c.dir, r68: c.r68_deg, r95: c.r95_deg } : null);
    // metrics
    const before = origPer(rid), after = (at.manifest.fusion.per_region || []).find((p) => p.id === rid) || {};
    const n2 = (x) => (x === null || x === undefined ? '–' : Math.max(0, x).toFixed(2));
    const a0 = (x) => (x === null || x === undefined ? '–' : `${x.toFixed(0)}°`);
    const fid = meta.fidelity || {};
    $('#atk-metrics', d.body).innerHTML = `
      <div class="metric"><div class="micro">Verdict</div><div class="mv">${chip(m.fusion.verdict, true)}<span class="arrow">→</span>${chip(meta.verdict, true)}</div><div class="md">${meta.verdict === 'SUSPICIOUS' ? 'still sent for human review' : 'would pass the lighting check'}</div></div>
      <div class="metric"><div class="micro">Image score S<sub>img</sub></div><div class="mv">${n2(m.fusion.S_img)}<span class="arrow">→</span>${n2(meta.S_img)}</div><div class="md">alert level ${state.cfg.tau_img.toFixed(2)}</div></div>
      <div class="metric"><div class="micro">${esc(reg.name)}: off consensus</div><div class="mv">${a0(before.angle_deg)}<span class="arrow">→</span>${a0(after.angle_deg)}</div><div class="md">shortfall ${n2(before.shortfall)} → ${n2(after.shortfall)}</div></div>
      <div class="metric"><div class="micro">Fidelity cost</div><div class="mv">${fid.mean_abs_dY !== undefined ? fid.mean_abs_dY.toFixed(3) : '–'}</div><div class="md">mean |ΔY| in region · SSIM loss ${fid.ssim_loss !== undefined ? fid.ssim_loss.toFixed(3) : '–'}</div></div>`;
    $('#atk-interp', d.body).innerHTML = `${ICONS.info}<div>${esc(meta.interpretation || at.manifest.description || '')} <span class="faint">${esc(REVIEW)}</span></div>`;
  }

  async function liveRun(variants, regionId) {
    const sigma = +($('#atk-sigma', d.body)?.value || 10);
    const bar = $('.attack-side .progress', d.body);
    if (bar) bar.hidden = false;
    try {
      const r = await fetch('/api/attack', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bundle: B.name, region: regionId, variants, sigma_att: sigma }) });
      if (!r.ok) throw new Error(`HTTP ${r.status} ${await r.text()}`);
      await r.json();
      const fresh = await ctx.reload();
      toast('Attack finished; bundle reloaded.');
      d.close();
      openAttackLab({ ...ctx, B: fresh });
    } catch (e) {
      toast(`Live attack failed: ${e.message}`, 'err', 8000);
    } finally { if (bar) bar.hidden = true; }
  }

  // swipe interaction
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
  $('#atk-region', d.body).value = String(rid);
  $('#atk-region', d.body).addEventListener('change', (e) => { rid = +e.target.value; const first = attacks.find((a) => a.region_id === rid); pick(first.variant); });
  const live = $('#atk-live', d.body);
  if (live) live.addEventListener('click', () => liveRun([cur ? cur.variant.split('_')[0] : 'T3a'], rid));
  window.addEventListener('resize', redraw);
  new ResizeObserver(redraw).observe($('#atk-stage', d.body));
  const firstT3 = attacks.find((a) => a.region_id === rid && a.variant.startsWith('T3a')) || attacks.find((a) => a.region_id === rid);
  await pick(firstT3.variant);
  renderSummary(await summaryP);

  function renderSummary(s) {
    const el = $('#summary', d.body);
    if (!el) return;
    if (!s || !Array.isArray(s.rows) || !s.rows.length) {
      el.innerHTML = '<div class="micro">Detection by attack tier (evaluation)</div><p class="faint" style="margin:6px 0 0">No evaluation summary yet (<span class="mono">data/results/attack_summary.json</span> is produced by <span class="mono">python -m lightaudit.cli eval</span>).</p>';
      return;
    }
    const pct = (x) => (typeof x === 'number' ? `${(x * 100).toFixed(0)}%` : '–');
    el.innerHTML = `<div class="micro">Detection by attack tier (evaluation)</div>
      <table class="summary-table" style="margin-top:6px"><thead><tr><th>Tier</th><th>Detected, shading only</th><th>Detected, all cues</th><th>Mean |ΔY|</th><th>n</th></tr></thead>
      <tbody>${s.rows.map((r) => `<tr><td>${esc(r.label || r.tier)}</td><td class="num">${pct(r.tpr_c1)}</td><td class="num">${pct(r.tpr_fused)}</td><td class="num">${typeof r.mean_abs_dY === 'number' ? r.mean_abs_dY.toFixed(3) : '–'}</td><td class="num">${esc(r.n ?? '–')}</td></tr>`).join('')}</tbody></table>
      ${s.caveat ? `<p class="faint" style="margin:6px 0 0;font-size:11.5px">${esc(s.caveat)}</p>` : ''}`;
  }
}
