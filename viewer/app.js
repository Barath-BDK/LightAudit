// LightAudit viewer entry point: routing (gallery | bundle), live fusion, wiring of the views.

import { state, prefs, loadBundle, fetchJSON, detectApi, BUNDLES } from './state.js';
import { D, dir, azElDeg, normalize, hpd, coneHalfAngleDeg } from './grid.js';
import { fuse, combineCues, logMaps, whatIf, displayShortfalls, mapArgmax, DEFAULT_CFG } from './fusion.js';
import { explain, reasonOf, esc, VERDICT_META } from './text.js';
import { ImageView, MODES, MODE_LABELS } from './relight.js';
import { Dome } from './dome.js';
import { $, $$, chip, toast, renderVerdict, renderTable, renderGallery, workspaceHTML, closeTopDialog, dialogOpen, openDialog, ICONS } from './ui.js';
import { openExplain, openHelp } from './explain.js';
import { openAttackLab } from './attack.js';
import { ShadowTool } from './shadow_tool.js';

const root = document.getElementById('root');
const params = new URLSearchParams(location.search);

function hexRgb(h) {
  const n = parseInt(h.replace('#', ''), 16);
  return [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255];
}

// ------------------------------------------------------------------ theme
function bindTheme(onChange) {
  const btn = $('#theme-btn');
  if (!btn) return;
  btn.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
    document.documentElement.dataset.theme = next;
    prefs.set('theme', next);
    btn.outerHTML = (/** rebuilt to swap the icon */ '');
    const nav = document.querySelector('.topbar nav');
    const light = next === 'light';
    nav.insertAdjacentHTML('beforeend', `<button class="btn ghost" id="theme-btn" aria-label="Switch to ${light ? 'dark' : 'light'} theme" title="Switch to ${light ? 'dark' : 'light'} theme">${light ? ICONS.moon : ICONS.sun}</button>`);
    bindTheme(onChange);
    $('#theme-btn').focus();
    if (onChange) onChange();
  });
}

// ------------------------------------------------------------------ gallery
async function showGallery() {
  document.title = 'LightAudit · Gallery';
  let index = [];
  try {
    index = await fetchJSON(`${BUNDLES}index.json`);
  } catch (e) {
    root.innerHTML = `<div class="load-screen"><div><h2>No bundles found</h2><p>Could not read <code>bundles/index.json</code> (${esc(e.message)}).<br>Build the demo bundles with <code>python -m lightaudit.cli demo-bundles</code> and serve the project root.</p></div></div>`;
    return;
  }
  renderGallery(root, { index, api: state.api, onUpload: openUpload });
  bindTheme();
  $('#help-btn').addEventListener('click', () => openHelp());
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeTopDialog();
    if (e.key === '?' && !dialogOpen()) openHelp();
  });
}

function openUpload() {
  const d = openDialog({ title: 'Audit your own photo', cls: 'narrow' });
  d.body.innerHTML = `<form class="upload-form" id="up-form">
    <p class="muted" style="margin:0">The server segments the photo, predicts surface directions with the available normal models, runs every cue and the fusion, and writes a new bundle. Outdoor photos with direct sunlight and several objects work best. A flag means "send for human review", never "this is fraud".</p>
    <div class="row"><label for="up-image">Photo (JPG/PNG, max 15 MB)</label><input id="up-image" name="image" type="file" accept="image/png,image/jpeg" required></div>
    <div class="row"><label for="up-roi">Optional ROI mask (panel mode)</label><input id="up-roi" name="roi" type="file" accept="image/png"></div>
    <div class="row"><label for="up-fov">Horizontal field of view (°)</label><input id="up-fov" name="fov" type="number" min="20" max="120" step="1" value="60"></div>
    <div class="row"><span></span><div><button class="btn accent" type="submit">Run audit</button></div></div>
    <div class="progress" hidden><i></i></div><div class="log" hidden aria-live="polite"></div></form>`;
  const form = $('#up-form', d.body);
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData();
    const img = $('#up-image', form).files[0];
    if (!img) return;
    if (img.size > 15 * 1024 * 1024) { toast('The photo is larger than 15 MB.', 'warn'); return; }
    fd.append('image', img);
    const roi = $('#up-roi', form).files[0];
    if (roi) fd.append('roi', roi);
    fd.append('fov', $('#up-fov', form).value);
    const bar = $('.progress', form), log = $('.log', form);
    bar.hidden = log.hidden = false;
    form.querySelector('button[type=submit]').disabled = true;
    try {
      const r = await fetch('/api/audit', { method: 'POST', body: fd });
      if (!r.ok) throw new Error(`upload failed: HTTP ${r.status} ${await r.text()}`);
      const { job_id: id } = await r.json();
      for (;;) {
        await new Promise((res) => setTimeout(res, 1000));
        const j = await (await fetch(`/api/jobs/${encodeURIComponent(id)}`, { cache: 'no-store' })).json();
        bar.firstElementChild.style.width = `${Math.round((j.progress || 0) * (j.progress > 1 ? 1 : 100))}%`;
        log.textContent = Array.isArray(j.log) ? j.log.join('\n') : (j.log || j.status);
        log.scrollTop = log.scrollHeight;
        if (j.status === 'done') { location.href = `?bundle=${encodeURIComponent(j.bundle)}`; return; }
        if (j.status === 'error') throw new Error('the audit failed on the server (see log)');
      }
    } catch (err) {
      toast(err.message, 'err', 8000);
      form.querySelector('button[type=submit]').disabled = false;
    }
  });
}

// ------------------------------------------------------------------ bundle view
let B, view, dome, shadow;
let exportFusion, lnCache = null, lnKey = '';
let lsFusion = null;
const sort = { key: 'id', dir: 1 };

function cfgFromManifest(m) {
  const c = m.calibration || {};
  return { ...DEFAULT_CFG, tau_img: c.tau_img ?? 2, tau_ref: c.tau_ref ?? c.tau_img ?? 2, w_min: c.w_min ?? 0.35, eps: c.eps ?? 1e-3,
    w_glint: c.w_glint ?? 0.5, w_contour: c.w_contour ?? 0.5, min_reliable: c.min_reliable ?? 3,
    broad_consensus_frac: c.broad_consensus_frac ?? 0.35,
    soft_contrast: c.soft_contrast ?? Infinity, tau_panel: c.tau_panel ?? Infinity,
    shadow_levels_max: c.shadow_levels_max ?? Infinity };
}

/** All regions entering the fusion: bundle regions + scene-level pseudo regions (shadow pairs). */
function allRegions() { return [...B.regions, ...state.pseudo]; }

function regionMaps() {
  const base = cfgFromManifest(B.manifest);
  const reweigh = B.cues && (state.cfg.w_glint !== base.w_glint || state.cfg.w_contour !== base.w_contour);
  const maps = B.regions.map((r, i) => {
    if (!reweigh || !r.cue_maps || r.cue_maps.shading === undefined) return B.A[i];
    const cm = r.cue_maps;
    return combineCues(B.cues[cm.shading], cm.glint !== undefined ? B.cues[cm.glint] : null,
      cm.contour !== undefined ? B.cues[cm.contour] : null, state.cfg);
  });
  return [...maps, ...state.pseudo.map((p) => p.A)];
}

function recompute() {
  const regs = allRegions();
  const A = regionMaps();
  const key = `${state.cfg.w_glint}|${state.cfg.w_contour}|${state.cfg.eps}|${state.pseudo.length}|${state.pseudoVersion || 0}`;
  if (key !== lnKey) { lnCache = logMaps(A, state.cfg.eps); lnKey = key; }
  const weights = regs.map((r) => r.weight);
  const excluded = regs.map((r, i) => !state.use[i]);
  const centers = regs.map((r) => r.center);
  const f = fuse(A, weights, excluded, state.cfg, centers,
    { lnA: lnCache, contrast: regs.map((r) => r.contrast ?? null), panel_z: regs.map((r) => r.panel_z ?? null), shadow_mid: regs.map((r) => r.shadow_mid ?? null) });
  f.text = explain(f, regs.map((r, i) => ({ name: r.name, cues: r.cues || [], reason: f.per_region[i].reliable ? null : reasonOf(r) })), state.cfg.eps);
  state.fusion = f;
  state.maps = A;
  state.display = displayShortfalls(f, A, weights, state.cfg, centers, lnCache);
  const base = cfgFromManifest(B.manifest);
  state.modified = state.pseudo.length > 0 || regs.some((r, i) => state.use[i] === !!r.excluded)
    || ['tau_img', 'w_min', 'w_glint', 'w_contour'].some((k) => Math.abs(state.cfg[k] - base[k]) > 1e-9);
  if (state.selected === null || state.selected >= regs.length) {
    state.selected = f.top_region ?? f.per_region.findIndex((p) => p.reliable);
    if (state.selected < 0) state.selected = 0;
  }
  updateWhatIf(false);
  updateImageParams();
  updateDome();
  renderPanels();
}

function updateWhatIf(render = true) {
  const regs = allRegions();
  state.whatIf = whatIf(state.maps, regs.map((r) => r.weight), regs.map((r, i) => !state.use[i]), state.light, state.cfg);
  if (render) renderPanels();
}

function renderPanels() {
  const regs = allRegions();
  renderVerdict($('#verdict-body'), { fusion: state.fusion, regions: regs, tau: state.cfg.tau_img, whatIf: state.whatIf,
    light: state.light, modified: state.modified, display: state.display, original: B.manifest.fusion.verdict });
  renderTable($('#region-rows'), { regions: regs, fusion: state.fusion, display: state.display, whatIf: state.whatIf,
    use: state.use, selected: state.selected, tau: state.cfg.tau_img, sort });
  $('#head-chip').innerHTML = chip(state.fusion.verdict, true);
  $('#live-tag').innerHTML = state.modified ? `<span class="live-tag">● live, your settings <button class="btn ghost sm" id="reset-btn">Reset</button></span>` : '';
  const rb = $('#reset-btn');
  if (rb) rb.addEventListener('click', resetSettings);
  $('#table-note').textContent = `${state.fusion.n_reliable} reliable of ${regs.length}`;
  const [az, el] = azElDeg(state.light);
  $('#light-readout').textContent = `az ${az.toFixed(1)}°  el ${el.toFixed(1)}°`;
  updateFoot();
}

function resetSettings() {
  state.cfg = cfgFromManifest(B.manifest);
  state.use = allRegions().map((r) => !r.excluded);
  recompute();
  const pop = $('#tune-pop');
  if (pop) { pop.remove(); $('#tune-btn').setAttribute('aria-expanded', 'false'); }
}

function updateImageParams() {
  const f = state.fusion, ef = exportFusion;
  const rows = B.regions.map((r, i) => {
    const p = ef.per_region[i];
    let ref;
    if (!ef.consensus) ref = r.center;
    else ref = p.flagged ? dir(p.ref_index) : ef.consensus.dir;
    const lp = f.per_region[i];
    const status = lp.excluded ? 2 : lp.flagged ? 3 : !lp.reliable ? 4 : 1;
    return { id: r.id, lut: r.g_lut, sigma: r.sigma ?? 0.015, slope: r.slope ?? 1, weight: r.weight,
      hasRes: !r.excluded && r.kind !== 'pseudo' && r.n_valid >= 10 && !!r.g_lut, ref: normalize(ref), color: hexRgb(r.color), status };
  });
  view.setRegions(rows);
  const selId = state.selected !== null && B.regions[state.selected] ? B.regions[state.selected].id : -1;
  view.set({ selected: selId, light: state.light });
  view.animatePulse = !matchMedia('(prefers-reduced-motion: reduce)').matches && f.flagged.length > 0;
}

function lsMaps() {
  return B.regions.map((r) => B.ls[r.landscape_index]);
}

function updateDome() {
  const regs = allRegions();
  const f = state.fusion;
  const ls = state.baseline === 'ls' && B.ls;
  const sel = state.selected;
  let hint = '';
  if (state.shell === 'selected' && sel !== null) {
    const map = ls && sel < B.regions.length ? B.ls[B.regions[sel].landscape_index] : state.maps[sel];
    let lo = Infinity, hi = -Infinity;
    for (let k = 0; k < D; k++) { if (map[k] < lo) lo = map[k]; if (map[k] > hi) hi = map[k]; }
    const flat = hi - lo < 0.05;
    dome.setShell(flat ? 'none' : 'map', map);
    hint = flat ? `${regs[sel].name}: flat light map, it does not constrain the light` : `${regs[sel].name}: light map`;
  } else if (state.shell === 'consensus') {
    const cm = ls ? lsFusion.consensus_map : f.consensus_map;
    dome.setShell(cm ? 'map' : 'none', cm);
  } else if (state.shell === 'all') {
    const maps = ls ? lsMaps() : state.maps;
    dome.setShell('overlay', null, regs.map((r, i) => ({ A: maps[i], color: r.color, ok: f.per_region[i]?.reliable }))
      .filter((o, i) => o.ok && i < maps.length));
  } else dome.setShell('none');
  if (state.shell === 'consensus') hint = 'consensus of the reliable regions';
  if (state.shell === 'all') hint = 'all reliable regions, in their colours';
  if (ls) hint += ' · baseline cue';
  let h = $('#dome-stage .dome-hint');
  if (!h) { h = document.createElement('div'); h.className = 'dome-hint'; $('#dome-stage').appendChild(h); }
  h.textContent = hint;
  const lsRegs = ls ? new Map(B.manifest.baseline_ls.regions.map((r) => [r.id, r])) : null;
  const cones = [];
  if (state.cones) {
    regs.forEach((r, i) => {
      const p = f.per_region[i];
      if (p.excluded || (!p.reliable && i !== sel)) return;
      const src = lsRegs && lsRegs.get(r.id) ? lsRegs.get(r.id) : r;
      if (!(src.r95_deg < 179) && !(src.r68_deg < 179)) return;
      cones.push({ center: src.center, r68: src.r68_deg, r95: src.r95_deg, color: r.color, flagged: p.flagged,
        selected: i === sel, dim: !p.reliable });
    });
  }
  const c = ls ? lsFusion.consensus : f.consensus;
  dome.setCones(cones, c ? { dir: c.dir, r68: c.r68_deg, r95: c.r95_deg } : null);
  dome.setLight(state.light);
}

function updateFoot() {
  const foot = $('#image-foot');
  if (!foot) return;
  const mode = state.mode;
  const desc = {
    observed: 'The audited photo.',
    regions: 'Region labels. Hatched = excluded, red outline = flagged, orange = selected.',
    relit: 'Each region re-shaded from its fitted light to your light with its own tone curve.',
    counterfactual: 'How each region should look under the consensus light (exported).',
    residual: 'Live |observed − predicted| at your light, in units of the expected noise.',
    normals: 'Estimated surface directions (RGB = xyz).',
  }[mode];
  foot.innerHTML = `<span>${esc(desc)}</span><span class="spacer"></span>${mode === 'residual'
    ? `<span class="faint">z 0</span><canvas class="legend-ramp" id="ramp" width="90" height="8" aria-hidden="true"></canvas><span class="faint">≥ ${(4 / state.heatGain).toFixed(1)}</span>` : ''}`;
  const ramp = $('#ramp');
  if (ramp) {
    const g = ramp.getContext('2d');
    const stops = ['#000004', '#320a5e', '#781c6d', '#bc3754', '#ed6925', '#fbb61a', '#fcffa4'];
    const lg = g.createLinearGradient(0, 0, 90, 0);
    stops.forEach((s, i) => lg.addColorStop(i / (stops.length - 1), s));
    g.fillStyle = lg; g.fillRect(0, 0, 90, 8);
  }
}

// ------------------------------------------------------------------ image view interaction
function setMode(m) {
  if (!MODES.includes(m)) return;
  const avail = { counterfactual: !!B.images.counterfactual, residual: !!B.images.normals && !!B.images.unc, normals: !!B.images.normals, relit: !!B.images.normals };
  if (avail[m] === false) { toast(`${MODE_LABELS[m]} needs files missing from this bundle.`, 'warn'); return; }
  state.mode = m;
  prefs.set('mode', m);
  $$('#mode-tabs button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.mode === m)));
  view.set({ mode: m });
  renderModeTools();
  updateFoot();
  updateSplit();
}

let heatResult = null;
function renderModeTools() {
  const t = $('#mode-tools');
  const stage = $('#image-stage');
  $$('.stage-badge', stage).forEach((x) => x.remove());
  if (state.mode === 'relit') {
    t.innerHTML = `<label class="sr-only" for="spec-sel">Highlight model</label><select class="sel" id="spec-sel" title="Add a specular highlight at your light">
      <option value="0">Matte (no highlight)</option><option value="1">Glossy: Blinn-Phong</option><option value="2">Glossy: GGX</option></select>`;
    const s = $('#spec-sel');
    s.value = String(view.opts.spec);
    s.addEventListener('change', () => view.set({ spec: +s.value }));
  } else if (state.mode === 'residual') {
    t.innerHTML = `<label class="check" title="Heat gain">Gain <input type="range" id="gain" min="0.5" max="4" step="0.1" value="${state.heatGain}" style="width:64px" aria-label="Heat gain"></label>`;
    $('#gain').addEventListener('input', (e) => { state.heatGain = +e.target.value; view.set({ heatGain: state.heatGain }); updateFoot(); });
    if (!heatResult && B.images.heat) heatResult = view.heatCheck();
    const atCons = state.fusion.consensus && Math.acos(Math.min(1, state.light.reduce((s, v, k) => s + v * state.fusion.consensus.dir[k], 0))) * 180 / Math.PI < 0.75;
    const ok = heatResult && heatResult.within8 >= 0.95;
    const badge = document.createElement('div');
    badge.className = `stage-badge ${ok ? 'ok' : 'warn'}`;
    badge.title = 'The GPU residual is rendered at each region\'s reference light (the consensus; leave-one-out consensus for flagged regions, as in the export) and compared pixel by pixel with heat.png. Small differences come from the 8-bit normal and uncertainty maps.';
    badge.innerHTML = heatResult
      ? `<span class="dot"></span>${ok ? 'Matches exported heat map' : 'Differs from exported heat map'}: ${(heatResult.within8 * 100).toFixed(1)}% of ${heatResult.n} px within ±8/255, mean |Δ| ${heatResult.meanAbs.toFixed(1)}${atCons ? ' · your light is at the consensus' : ' · showing your light (snap to consensus to compare)'}`
      : '<span class="dot"></span>No exported heat map in this bundle';
    stage.appendChild(badge);
  } else t.innerHTML = '';
}

function bindImage() {
  const canvas = $('#image-canvas'), tip = $('#image-tip'), stage = $('#image-stage');
  const regs = () => allRegions();
  canvas.addEventListener('click', (e) => {
    const p = view.toImage(e.clientX, e.clientY);
    if (!p) return;
    if (shadow && shadow.active) { shadow.click(p); return; }
    const info = view.inspect(p[0], p[1]);
    if (info.index >= 0) select(info.index);
  });
  canvas.addEventListener('mousemove', (e) => {
    const p = view.toImage(e.clientX, e.clientY);
    if (!p || (shadow && shadow.active)) { tip.classList.remove('on'); view.set({ hover: -1 }); return; }
    const info = view.inspect(p[0], p[1]);
    view.set({ hover: info.id > 0 ? info.id : -1 });
    const r = info.index >= 0 ? regs()[info.index] : null;
    const pr = r ? state.fusion.per_region[info.index] : null;
    const d = r ? state.display[info.index] : null;
    const st = r ? (pr.excluded ? 'excluded' : pr.flagged ? 'FLAGGED' : !pr.reliable ? `unreliable: ${reasonOf(r)}` : 'reliable') : '';
    tip.innerHTML = r
      ? `<div class="t-head"><span class="swatch" style="background:${esc(r.color)}"></span>${esc(r.name)}</div>
         <div class="row"><span>status</span><span>${esc(st)}</span></div>
         ${d && d.shortfall !== null ? `<div class="row"><span>shortfall</span><span>${Math.max(0, d.shortfall).toFixed(2)} (alert ${state.cfg.tau_img.toFixed(2)})</span></div>` : ''}
         ${d && d.angle_deg !== null ? `<div class="row"><span>angle to consensus</span><span>${d.angle_deg.toFixed(0)}°</span></div>` : ''}
         <div class="row"><span>pixel (u, v)</span><span>${Math.floor(p[0])}, ${Math.floor(p[1])}</span></div>
         <div class="row"><span>luminance Y</span><span>${info.Y.toFixed(3)}</span></div>
         ${info.z !== undefined ? `<div class="row"><span>n·l at your light</span><span>${info.ndotl.toFixed(3)}</span></div>
         <div class="row"><span>predicted Y</span><span>${info.Yhat.toFixed(3)}</span></div>
         <div class="row"><span>residual z</span><span>${info.z.toFixed(2)}</span></div>
         <div class="row"><span>normal uncertainty</span><span>${info.unc.toFixed(1)}°</span></div>` : ''}`
      : `<div class="t-head faint">Unassigned pixel</div><div class="row"><span>luminance Y</span><span>${info.Y.toFixed(3)}</span></div>`;
    const sb = stage.getBoundingClientRect();
    let x = e.clientX - sb.left + 14, y = e.clientY - sb.top + 14;
    tip.classList.add('on');
    if (x + tip.offsetWidth > sb.width - 6) x = e.clientX - sb.left - tip.offsetWidth - 14;
    if (y + tip.offsetHeight > sb.height - 6) y = Math.max(6, e.clientY - sb.top - tip.offsetHeight - 14);
    tip.style.left = `${x}px`; tip.style.top = `${y}px`;
  });
  canvas.addEventListener('mouseleave', () => { tip.classList.remove('on'); view.set({ hover: -1 }); });
}

// split view
let splitEl = null;
function updateSplit() {
  const stage = $('#image-stage');
  const on = state.split && state.mode !== 'observed';
  $('#split-btn').setAttribute('aria-pressed', String(state.split));
  if (!on) {
    if (splitEl) { splitEl.forEach((x) => x.remove()); splitEl = null; }
    view.set({ split: 0 });
    return;
  }
  if (!splitEl) {
    const h = document.createElement('div');
    h.className = 'split-handle';
    h.setAttribute('role', 'slider');
    h.setAttribute('tabindex', '0');
    h.setAttribute('aria-label', 'Split position');
    h.innerHTML = '<span>⇔</span>';
    const l1 = document.createElement('div'); l1.className = 'split-label';
    const l2 = document.createElement('div'); l2.className = 'split-label';
    stage.append(h, l1, l2);
    splitEl = [h, l1, l2];
    const move = (clientX) => {
      const r = view.cssRect(), sb = stage.getBoundingClientRect();
      state.splitPos = Math.max(0, Math.min(1, (clientX - sb.left - r.x) / r.w));
      placeSplit();
    };
    h.addEventListener('pointerdown', (e) => { h.setPointerCapture(e.pointerId); h.onpointermove = (ev) => move(ev.clientX); });
    h.addEventListener('pointerup', () => { h.onpointermove = null; });
    h.addEventListener('keydown', (e) => {
      const d = e.key === 'ArrowLeft' ? -0.05 : e.key === 'ArrowRight' ? 0.05 : 0;
      if (!d) return;
      e.preventDefault(); e.stopPropagation();
      state.splitPos = Math.max(0, Math.min(1, state.splitPos + d));
      placeSplit();
    });
  }
  placeSplit();
}
function placeSplit() {
  if (!splitEl) return;
  const r = view.cssRect();
  const [h, l1, l2] = splitEl;
  const x = r.x + state.splitPos * r.w;
  h.style.left = `${x}px`;
  h.style.top = `${r.y}px`; h.style.bottom = 'auto'; h.style.height = `${r.h}px`;
  h.setAttribute('aria-valuenow', String(Math.round(state.splitPos * 100)));
  l1.textContent = 'Observed'; l1.style.left = `${r.x + 8}px`; l1.style.top = `${r.y + 8}px`;
  l2.textContent = MODE_LABELS[state.mode]; l2.style.left = 'auto'; l2.style.right = `${view.canvas.clientWidth - r.x - r.w + 8}px`; l2.style.top = `${r.y + 8}px`;
  view.set({ split: state.splitPos });
}

function select(i) {
  state.selected = i;
  const r = allRegions()[i];
  if (r && state.shell === 'none') { /* keep the user's shell choice */ }
  updateImageParams();
  updateDome();
  renderPanels();
}

let lightRaf = 0;
function setLight(l) {
  state.light = normalize(l);
  view.set({ light: state.light });
  if (lightRaf) return;
  lightRaf = requestAnimationFrame(() => {
    lightRaf = 0;
    dome.setLight(state.light);
    updateWhatIf(true);
    if (state.mode === 'residual') renderModeTools();
  });
}

function openTune() {
  const btn = $('#tune-btn');
  const existing = $('#tune-pop');
  if (existing) { existing.remove(); btn.setAttribute('aria-expanded', 'false'); return; }
  btn.setAttribute('aria-expanded', 'true');
  const pop = document.createElement('div');
  pop.className = 'popover';
  pop.id = 'tune-pop';
  pop.setAttribute('role', 'dialog');
  pop.setAttribute('aria-label', 'Cue weights and thresholds');
  const c = state.cfg, hasCues = !!B.cues;
  const field = (id, label, min, max, step, val, hint, disabled = false) => `<div class="field"><label for="${id}">${label}</label><output id="${id}-o">${val.toFixed(2)}</output>
    <input type="range" id="${id}" min="${min}" max="${max}" step="${step}" value="${val}" ${disabled ? 'disabled' : ''}><span class="hint">${hint}</span></div>`;
  pop.innerHTML = `<h3 class="micro">Cue weights &amp; thresholds</h3>
    ${field('t-wg', 'Specular highlight weight w<sub>glint</sub>', 0, 1, 0.05, c.w_glint, hasCues ? 'How much glints shape a region\'s map.' : 'Not available: bundle has no separate cue maps.', !hasCues)}
    ${field('t-wc', 'Silhouette weight w<sub>contour</sub>', 0, 1, 0.05, c.w_contour, hasCues ? 'How much silhouette normals shape a region\'s map.' : 'Not available.', !hasCues)}
    ${field('t-tau', 'Alert level τ', 0.5, 6.9, 0.05, c.tau_img, `Calibrated: ${cfgFromManifest(B.manifest).tau_img.toFixed(2)} (false-alarm control on the calibration set).`)}
    ${field('t-wmin', 'Reliability floor w<sub>min</sub>', 0, 0.95, 0.01, c.w_min, 'Regions below this weight are not used.')}
    <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:6px"><button class="btn sm" id="t-reset">Reset to calibrated</button></div>`;
  $('#verdict-panel').appendChild(pop);
  pop.style.right = '10px'; pop.style.top = '40px';
  let t = 0;
  const bind = (id, key) => {
    const el = $(`#${id}`, pop);
    el.addEventListener('input', () => {
      state.cfg = { ...state.cfg, [key]: +el.value };
      if (key === 'tau_img') state.cfg.tau_ref = +el.value * ((B.manifest.calibration.tau_ref ?? 1) / (B.manifest.calibration.tau_img || 1));
      $(`#${id}-o`, pop).textContent = (+el.value).toFixed(2);
      clearTimeout(t);
      t = setTimeout(recompute, 30);
    });
  };
  bind('t-wg', 'w_glint'); bind('t-wc', 'w_contour'); bind('t-tau', 'tau_img'); bind('t-wmin', 'w_min');
  $('#t-reset', pop).addEventListener('click', resetSettings);
  $('input', pop).focus();
}

function bindWorkspace() {
  $$('#mode-tabs button').forEach((b) => b.addEventListener('click', () => setMode(b.dataset.mode)));
  $('#mode-tabs').addEventListener('keydown', (e) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    e.preventDefault(); e.stopPropagation();
    const i = MODES.indexOf(state.mode) + (e.key === 'ArrowRight' ? 1 : -1);
    setMode(MODES[(i + MODES.length) % MODES.length]);
    $(`#mode-tabs button[data-mode="${state.mode}"]`).focus();
  });
  const shellSel = $('#shell-sel');
  shellSel.value = state.shell;
  shellSel.addEventListener('change', () => { state.shell = shellSel.value; prefs.set('shell', state.shell); updateDome(); });
  const cb = $('#cones-cb');
  cb.checked = state.cones;
  cb.addEventListener('change', () => { state.cones = cb.checked; prefs.set('cones', state.cones); updateDome(); });
  $$('#baseline-seg button').forEach((b) => b.addEventListener('click', () => {
    state.baseline = b.dataset.b;
    $$('#baseline-seg button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    updateDome();
    if (state.baseline === 'ls') toast(`Baseline cue "${B.manifest.baseline_ls.cue || 'ls'}" (comparison only): its own verdict would be ${lsFusion.verdict}. The audit uses the "${B.manifest.cue || 'rank'}" cue.`);
  }));
  $('#snap-cons').addEventListener('click', () => { if (state.fusion.consensus) setLight(state.fusion.consensus.dir); else toast('No consensus: fewer than one reliable region.', 'warn'); });
  $('#snap-sel').addEventListener('click', () => {
    const r = allRegions()[state.selected];
    if (r && r.r68_deg < 179) setLight(r.center); else toast('The selected region has no usable light estimate.', 'warn');
  });
  $('#split-btn').addEventListener('click', () => { state.split = !state.split; if (state.split && state.mode === 'observed') setMode('relit'); updateSplit(); });
  $('#shadow-btn').addEventListener('click', () => shadow.toggle());
  $('#tune-btn').addEventListener('click', openTune);
  $('#explain-btn').addEventListener('click', () => openExplain(ctx()));
  $('#attack-btn').addEventListener('click', () => openAttackLab(ctx()));
  $('#help-btn').addEventListener('click', () => openHelp());
  const tbody = $('#region-rows');
  tbody.addEventListener('change', (e) => {
    const i = e.target.dataset.use;
    if (i === undefined) return;
    state.use[+i] = e.target.checked;
    recompute();
  });
  tbody.addEventListener('click', (e) => {
    if (e.target.closest('input')) return;
    const tr = e.target.closest('tr[data-i]');
    if (tr) select(+tr.dataset.i);
  });
  tbody.addEventListener('keydown', (e) => {
    const tr = e.target.closest('tr[data-i]');
    if (!tr || e.target.tagName === 'INPUT') return;
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(+tr.dataset.i); $(`tr[data-i="${tr.dataset.i}"]`, tbody).focus(); }
  });
  tbody.addEventListener('mouseover', (e) => {
    const tr = e.target.closest('tr[data-i]');
    const r = tr && B.regions[+tr.dataset.i];
    view.set({ hover: r ? r.id : -1 });
  });
  tbody.addEventListener('mouseleave', () => view.set({ hover: -1 }));
  $$('th[data-sort] button').forEach((b) => b.addEventListener('click', () => {
    const th = b.parentElement, k = th.dataset.sort;
    sort.dir = sort.key === k ? -sort.dir : (k === 'name' ? 1 : -1);
    sort.key = k;
    $$('th[data-sort]').forEach((x) => x.removeAttribute('aria-sort'));
    th.setAttribute('aria-sort', sort.dir > 0 ? 'ascending' : 'descending');
    renderPanels();
  }));
  bindTheme(() => { dome.applyTheme(); });
  document.addEventListener('keydown', onKey);
  document.addEventListener('mousedown', (e) => {
    const pop = $('#tune-pop');
    if (pop && !pop.contains(e.target) && !e.target.closest('#tune-btn')) { pop.remove(); $('#tune-btn').setAttribute('aria-expanded', 'false'); }
  });
}

function onKey(e) {
  if (e.key === 'Escape') {
    const pop = $('#tune-pop');
    if (closeTopDialog()) return;
    if (pop) { pop.remove(); $('#tune-btn').setAttribute('aria-expanded', 'false'); $('#tune-btn').focus(); return; }
    if (shadow && shadow.active) { shadow.toggle(false); return; }
    return;
  }
  if (dialogOpen() || e.ctrlKey || e.metaKey || e.altKey) return;
  const tag = (e.target.tagName || '').toLowerCase();
  if (tag === 'input' || tag === 'select' || tag === 'textarea') return;
  const k = e.key;
  if (k >= '1' && k <= '6') { setMode(MODES[+k - 1]); return; }
  const lower = k.toLowerCase();
  if (lower === 'r') { view.set({ outline: view.opts.outline ? 0 : 1 }); toast(`Region outlines ${view.opts.outline ? 'on' : 'off'}`, 'info', 1500); return; }
  if (lower === 'h') { setMode(state.mode === 'residual' ? (state.prevMode || 'observed') : (state.prevMode = state.mode, 'residual')); return; }
  if (lower === 'c') { state.cones = !state.cones; $('#cones-cb').checked = state.cones; prefs.set('cones', state.cones); updateDome(); return; }
  if (lower === 'e') { openExplain(ctx()); return; }
  if (lower === 'a') { openAttackLab(ctx()); return; }
  if (k === '?') { openHelp(); return; }
  const d = { ArrowLeft: [-2, 0], ArrowRight: [2, 0], ArrowUp: [0, 2], ArrowDown: [0, -2] }[k];
  if (d && !e.target.closest('table, .seg, .split-handle')) { e.preventDefault(); dome.nudge(d[0], d[1]); }
}

/** Context handed to the explain stepper and the attack lab. */
function ctx() {
  return { B, state, view, allRegions, exportFusion, cfgFromManifest, reload: reloadBundle };
}

async function reloadBundle() {
  B = await loadBundle(B.name);
  view.setBundle(B);
  recompute();
  return B;
}

async function showBundle(name) {
  root.innerHTML = `<div class="load-screen"><div><div class="micro">LightAudit</div><p>Loading <b>${esc(name)}</b>...</p><div class="progress"><i id="lp"></i></div></div></div>`;
  try {
    B = await loadBundle(name, (p) => { const i = $('#lp'); if (i) i.style.width = `${Math.round(p * 100)}%`; });
  } catch (e) {
    root.innerHTML = `<div class="load-screen"><div><h2>Could not load "${esc(name)}"</h2><p class="muted">${esc(e.message)}</p><p><a class="btn" href="index.html">Back to the gallery</a></p></div></div>`;
    return;
  }
  document.title = `LightAudit · ${B.manifest.title}`;
  root.innerHTML = workspaceHTML(B);
  state.cfg = cfgFromManifest(B.manifest);
  state.use = B.regions.map((r) => !r.excluded);
  const regs = B.regions;
  exportFusion = fuse(B.A, regs.map((r) => r.weight), regs.map((r) => r.excluded), state.cfg, regs.map((r) => r.center),
    { contrast: regs.map((r) => r.contrast ?? null), panel_z: regs.map((r) => r.panel_z ?? null), shadow_mid: regs.map((r) => r.shadow_mid ?? null) });
  if (B.ls) {
    const lsr = new Map(B.manifest.baseline_ls.regions.map((r) => [r.id, r]));
    lsFusion = fuse(lsMaps(), regs.map((r) => (lsr.get(r.id) || r).weight), regs.map((r) => r.excluded), state.cfg,
      regs.map((r) => (lsr.get(r.id) || r).center));
  }
  state.light = exportFusion.consensus ? exportFusion.consensus.dir.slice() : normalize([0.4, 0.7, 0.6]);
  try {
    view = new ImageView($('#image-canvas'));
  } catch (e) {
    root.innerHTML = `<div class="load-screen"><div><h2>WebGL2 is not available</h2><p class="muted">${esc(e.message)}</p></div></div>`;
    return;
  }
  view.setBundle(B);
  view.onResize = () => { placeSplit(); if (shadow) shadow.draw(); };
  dome = new Dome($('#dome-stage'), { onLight: (l) => setLight(l) });
  dome.setPhoto(B.images.image.bitmap, B.W, B.H);
  shadow = new ShadowTool({ stage: $('#image-stage'), canvas: $('#image-overlay'), view, bundle: B, cfg: () => state.cfg,
    button: $('#shadow-btn'), onChange: (pseudo) => {
      const n = B.regions.length;
      state.pseudo = pseudo ? [pseudo] : [];
      state.pseudoVersion = (state.pseudoVersion || 0) + 1;
      state.use = [...state.use.slice(0, n), ...state.pseudo.map(() => true)];
      if (state.selected >= n + state.pseudo.length) state.selected = null;
      recompute();
    } });
  bindWorkspace();
  bindImage();
  recompute();
  setMode(MODES.includes(state.mode) ? state.mode : 'observed');
  if (B.missing.length) toast(`Optional files missing from this bundle: ${B.missing.join(', ')}. Related views are disabled.`, 'warn', 8000);
  window.__lightaudit = { state, get B() { return B; }, view, dome, exportFusion };
}

async function main() {
  state.api = await detectApi();
  const name = params.get('bundle');
  if (name) await showBundle(name);
  else await showGallery();
}

main().catch((e) => {
  root.innerHTML = `<div class="load-screen"><div><h2>Something went wrong</h2><p class="muted">${esc(e.message)}</p><p><a class="btn" href="index.html">Back to the gallery</a></p></div></div>`;
  throw e;
});

export { VERDICT_META, hpd, coneHalfAngleDeg, mapArgmax, D };
