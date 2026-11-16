// DOM building blocks: icons, verdict chip/banner, region table, gallery, toasts, overlays.

import { VERDICT_META, REVIEW, esc, richText, reasonOf, whatIfText, CUE_NAMES, explain } from './text.js';
import { azElDeg } from './grid.js';
import { asciiBackground } from './ascii_bg.js';

export const ICONS = {
  CONSISTENT: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="8" cy="8" r="6.5"/><path d="M5 8.2l2 2 4-4.2"/></svg>',
  SUSPICIOUS: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M8 1.8l6.6 11.7H1.4z" stroke-linejoin="round"/><path d="M8 6.2v3.6M8 11.6v.4" stroke-linecap="round"/></svg>',
  INSUFFICIENT: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="8" cy="8" r="6.5" stroke-dasharray="2.4 1.8"/><path d="M5 8h6" stroke-linecap="round"/></svg>',
  CONFLICT: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M8 1.5l6.5 6.5L8 14.5 1.5 8z" stroke-linejoin="round"/><path d="M5.6 6.6h4.8M5.6 9.4h4.8" stroke-linecap="round"/></svg>',
  brand: '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.6" opacity=".55"/><path d="M3 12h18" stroke="currentColor" stroke-width="1.2" opacity=".35"/><circle cx="17" cy="7" r="2.6" fill="var(--accent)"/><path d="M12 12L16 8" stroke="var(--accent)" stroke-width="1.6" stroke-linecap="round"/></svg>',
  close: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8" stroke-linecap="round"/></svg>',
  sun: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><circle cx="8" cy="8" r="3"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.4 1.4M11.6 11.6L13 13M3 13l1.4-1.4M11.6 4.4L13 3" stroke-linecap="round"/></svg>',
  moon: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M13 9.5A5.5 5.5 0 016.5 3a5.5 5.5 0 106.5 6.5z" stroke-linejoin="round"/></svg>',
  grid: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><rect x="2" y="2" width="5" height="5"/><rect x="9" y="2" width="5" height="5"/><rect x="2" y="9" width="5" height="5"/><rect x="9" y="9" width="5" height="5"/></svg>',
  steps: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><circle cx="3" cy="8" r="1.6"/><circle cx="8" cy="8" r="1.6"/><circle cx="13" cy="8" r="1.6"/><path d="M4.6 8h1.8M9.6 8h1.8"/></svg>',
  target: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="2.5"/><path d="M8 0v3M8 13v3M0 8h3M13 8h3"/></svg>',
  help: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><circle cx="8" cy="8" r="6.5"/><path d="M6.2 6.2a1.9 1.9 0 113 1.5c-.8.5-1.2.9-1.2 1.8M8 11.6v.4" stroke-linecap="round"/></svg>',
  tune: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M2 4h7M12 4h2M2 12h3M8 12h6" stroke-linecap="round"/><circle cx="10.5" cy="4" r="1.5"/><circle cx="6.5" cy="12" r="1.5"/></svg>',
  upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M12 16V4M7 9l5-5 5 5" stroke-linecap="round" stroke-linejoin="round"/><path d="M4 15v4h16v-4" stroke-linecap="round"/></svg>',
  check: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  cross: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8" stroke-linecap="round"/></svg>',
  info: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><circle cx="8" cy="8" r="6.5"/><path d="M8 7v4.5M8 4.6v.4" stroke-linecap="round"/></svg>',
  shadow: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M3 13L13 3" stroke-dasharray="2 2"/><circle cx="3" cy="13" r="1.6"/><circle cx="9" cy="7" r="1.6"/></svg>',
  split: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><rect x="1.5" y="2.5" width="13" height="11" rx="1"/><path d="M8 2.5v11"/></svg>',
};

export function chip(verdict, small = false) {
  const m = VERDICT_META[verdict] || { word: verdict };
  return `<span class="chip v-${esc(verdict)}"${small ? ' style="height:19px;font-size:10px"' : ''}>${ICONS[verdict] || ''}${esc(verdict.charAt(0) + verdict.slice(1).toLowerCase())}</span>`;
}

export function $(sel, root = document) { return root.querySelector(sel); }
export function $$(sel, root = document) { return [...root.querySelectorAll(sel)]; }

export function toast(msg, kind = 'info', ms = 5000) {
  const host = document.getElementById('toasts');
  if (!host) return;
  const t = document.createElement('div');
  t.className = `toast ${kind}`;
  t.innerHTML = `${kind === 'info' ? ICONS.info : ICONS.SUSPICIOUS}<div>${esc(msg)}</div>`;
  t.querySelector('svg').style.cssText = 'width:15px;height:15px;flex:none;margin-top:1px';
  host.appendChild(t);
  setTimeout(() => t.remove(), ms);
}

export function themeButton() {
  const light = document.documentElement.dataset.theme === 'light';
  return `<button class="btn ghost" id="theme-btn" aria-label="Switch to ${light ? 'dark' : 'light'} theme" title="Switch to ${light ? 'dark' : 'light'} theme">${light ? ICONS.moon : ICONS.sun}</button>`;
}

// ------------------------------------------------------------------ overlays (dialogs)
let openStack = [];
/** Opens a modal dialog. Returns { el, body, close }. Esc closes the topmost one; focus is restored. */
export function openDialog({ title, cls = '', head = '', foot = '', onClose }) {
  const prev = document.activeElement;
  const ov = document.createElement('div');
  ov.className = 'overlay';
  ov.innerHTML = `<div class="dialog ${cls}" role="dialog" aria-modal="true" aria-label="${esc(title)}">
    <div class="dialog-head"><h2>${esc(title)}</h2>${head}<span class="spacer"></span>
    <button class="btn ghost" data-close aria-label="Close (Esc)" title="Close (Esc)">${ICONS.close}</button></div>
    <div class="dialog-body"></div>${foot ? `<div class="dialog-foot">${foot}</div>` : ''}</div>`;
  document.body.appendChild(ov);
  const d = { el: ov, body: ov.querySelector('.dialog-body'), dialog: ov.querySelector('.dialog') };
  d.close = () => {
    if (!ov.isConnected) return;
    ov.remove();
    openStack = openStack.filter((x) => x !== d);
    if (onClose) onClose();
    if (prev && prev.focus) prev.focus();
  };
  ov.addEventListener('mousedown', (e) => { if (e.target === ov) d.close(); });
  ov.querySelector('[data-close]').addEventListener('click', d.close);
  ov.addEventListener('keydown', (e) => {   // simple focus trap
    if (e.key !== 'Tab') return;
    const f = $$('button, [href], input, select, [tabindex]:not([tabindex="-1"])', d.dialog).filter((x) => !x.disabled && x.offsetParent);
    if (!f.length) return;
    if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
    else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
  });
  openStack.push(d);
  setTimeout(() => ov.querySelector('[data-close]').focus(), 0);
  return d;
}
export function closeTopDialog() {
  const d = openStack[openStack.length - 1];
  if (d) { d.close(); return true; }
  return false;
}
export function dialogOpen() { return openStack.length > 0; }

// ------------------------------------------------------------------ verdict panel
export function renderVerdict(el, { fusion, regions, tau, whatIf, light, modified, display, original }) {
  const v = fusion.verdict;
  const m = VERDICT_META[v];
  const sMax = 6.91;
  const s = fusion.n_reliable ? fusion.S_img : 0;
  const notAssessed = regions.map((r, i) => ({ r, p: fusion.per_region[i] }))
    .filter(({ p, r }) => !p.reliable && r.kind !== 'pseudo');
  const [az, elv] = azElDeg(light);
  el.innerHTML = `
    <div class="verdict-main">
    <div class="verdict-banner v-${v}" aria-live="polite">
      <div class="vicon">${ICONS[v]}</div>
      <div><div class="micro" style="color:inherit;opacity:.85">${modified ? 'Live audit verdict (your settings)' : 'Audit verdict'}</div>
        <div class="vword">${esc((VERDICT_META[v] || { word: v }).word)}</div></div>
      <div class="vscore" title="Image score S_img: the largest leave-one-out shortfall among reliable regions. Above the alert level means a region does not fit the light the others agree on.">S<sub>img</sub><b>${fusion.n_reliable ? s.toFixed(2) : '–'}</b>alert ${tau.toFixed(2)}</div>
      <div class="vsub">${esc(m.action)}</div>
    </div>
    <div class="verdict-section">
      <div class="gauge v-${v}" role="img" aria-label="Image score ${s.toFixed(2)} against alert level ${tau.toFixed(2)}">
        <div class="fill" style="width:${Math.min(100, s / sMax * 100).toFixed(1)}%"></div>
        <div class="tau" style="left:${Math.min(100, tau / sMax * 100).toFixed(1)}%" title="alert level ${tau.toFixed(2)}"></div>
      </div>
      <div class="gauge-scale"><span>0 · full agreement</span><span>shortfall</span><span>6.9 · no overlap</span></div>
    </div>
    </div>
    <div class="verdict-detail">
    <div class="verdict-section">
      <div class="micro" style="margin-bottom:4px">Why</div>
      <p class="why">${richText(fusion.text)}</p>
      <div class="review-note">${fusion.text.includes(REVIEW) ? '' : esc(REVIEW)}${original && modified ? ` Exported verdict for this bundle: <b>${esc(original)}</b>.` : ''}</div>
    </div>
    <div class="verdict-section">
      <div class="whatif"><span class="micro">What-if at your light</span>
        <span class="mono">az ${az.toFixed(0)}°, el ${elv.toFixed(0)}°</span>
        ${whatIf ? chip(whatIf.verdict, true) : ''}</div>
      <div class="whatif" style="margin-top:3px">${whatIf ? esc(whatIfText(whatIf, regions)) : ''}</div>
    </div>
    ${notAssessed.length ? `<div class="verdict-section not-assessed"><div class="micro">Could not be assessed (never flagged)</div><ul>${
      notAssessed.map(({ r, p }) => `<li>${esc(r.name)}: <span class="faint">${p.excluded ? 'excluded' + (r.reason ? ` (${esc(r.reason)})` : '') : esc(reasonOf(r))}</span></li>`).join('')}</ul></div>` : ''}
    </div>`;
}

// ------------------------------------------------------------------ region table
export function statusOf(r, p, fusion, tau, disp) {
  if (p.excluded) return { key: 'excl', text: 'excluded', order: 4 };
  if (!p.reliable) return { key: 'unrel', text: `unreliable: ${reasonOf(r)}`, order: 3 };
  if (p.flagged) return { key: 'flag', text: 'Flagged', order: 0 };
  const s = disp ? disp.shortfall : p.shortfall;
  if (fusion.verdict === 'INSUFFICIENT') return { key: 'unrel', text: 'not decided', order: 2 };
  if (s !== null && s > tau) return { key: 'disagree', text: 'disagrees', order: 1 };
  return { key: 'ok', text: 'agrees', order: 2 };
}

export function renderTable(tbody, { regions, fusion, display, whatIf, use, selected, tau, sort }) {
  const rows = regions.map((r, i) => {
    const p = fusion.per_region[i], d = display[i];
    return { r, i, p, d, st: statusOf(r, p, fusion, tau, d), like: whatIf ? whatIf.per_region[i].agreement : null };
  });
  const key = sort.key, dir = sort.dir;
  const val = (x) => ({
    name: x.r.name.toLowerCase(), weight: x.r.weight, shortfall: x.d.shortfall ?? -1, angle: x.d.angle_deg ?? -1,
    like: x.like ?? -1, status: x.st.order, id: x.i,
  })[key];
  rows.sort((a, b) => {
    const A = val(a), B = val(b);
    return (A < B ? -1 : A > B ? 1 : a.i - b.i) * dir;
  });
  const sMax = 6.91;
  tbody.innerHTML = rows.map(({ r, i, p, d, st, like }) => {
    const s = d.shortfall;
    const cues = (r.cues || []).map((c) => `<span class="cue ${c === 'shadow' ? 'p' : ''}" title="${esc(CUE_NAMES[c] || c)} cue">${{ shading: 'S', glint: 'G', contour: 'C', shadow: 'P' }[c] || '?'}</span>`).join('');
    const stIcon = st.key === 'flag' ? ICONS.SUSPICIOUS : st.key === 'ok' ? ICONS.check : '';
    const dim = !p.reliable;
    return `<tr data-i="${i}" aria-selected="${selected === i}" class="${dim ? 'dim' : ''}" tabindex="0">
      <td><input type="checkbox" data-use="${i}" ${use[i] ? 'checked' : ''} aria-label="Use ${esc(r.name)} in the fusion"></td>
      <td><div class="rname"><span class="swatch" style="background:${esc(r.color)}"></span><span class="n" title="${esc(r.name)}">${esc(r.name)}</span>${r.kind === 'pseudo' ? '<span class="exp-badge">exp.</span>' : ''}</div></td>
      <td title="reliability weight (geometric mean of five factors); regions below ${'w_min'} are not used"><span class="bar"><i style="width:${(r.weight * 100).toFixed(0)}%"></i></span><span class="num">${r.weight.toFixed(2)}</span></td>
      <td title="${d.ref ? 'shortfall within the reference set (flagged regions removed)' : 'leave-one-out shortfall'}: 0 = fully agrees, 6.9 = no overlap; alert ${tau.toFixed(2)}">${s === null || s === undefined ? '<span class="faint">–</span>' :
        `<span class="bar sf ${s > tau && p.reliable ? 'over' : ''}"><i style="width:${Math.min(100, Math.max(0, s) / sMax * 100).toFixed(0)}%"></i><span class="alert" style="left:${Math.min(100, tau / sMax * 100).toFixed(0)}%"></span></span><span class="num">${Math.max(0, s).toFixed(2)}</span>`}</td>
      <td class="num" title="angle between this region's own estimate and the consensus of the other regions">${d.angle_deg === null || d.angle_deg === undefined ? '<span class="faint">–</span>' : d.angle_deg.toFixed(0) + '°'}</td>
      <td title="how much this region likes your light: its map value A_k at your light (1 = best)">${like === null || p.excluded ? '<span class="faint">–</span>' : `<span class="bar like"><i style="width:${(like * 100).toFixed(0)}%"></i></span><span class="num">${like.toFixed(2)}</span>`}</td>
      <td>${cues}</td>
      <td><span class="status ${st.key}">${stIcon}${esc(st.text)}</span></td>
    </tr>`;
  }).join('');
}

// ------------------------------------------------------------------ gallery
export function renderGallery(root, { index, api, onUpload }) {
  const cards = index.map((b, i) => {
    const fail = /failure/i.test(b.name);
    return `<a class="card ${fail ? 'failure' : ''}" data-reveal href="?bundle=${encodeURIComponent(b.name)}">
      <div class="thumb"><img src="../bundles/${esc(b.thumb || `${b.name}/thumb.jpg`)}" alt="" loading="lazy" width="320" height="220">
        ${chip(b.verdict)}<span class="tag src">${esc(b.source || 'synthetic')}</span></div>
      <div class="body"><h3>${esc(b.title)}</h3><p>${esc(b.description)}</p><div class="meta">${esc(b.name)}</div></div></a>`;
  }).join('');
  // featured audit for the hero: a real photo with a caught paste, else the first real or flagged bundle
  const featured = index.find((b) => b.name === 'real_mit_pear_spliced')
    || index.find((b) => b.source === 'real' && b.verdict === 'SUSPICIOUS') || index.find((b) => b.verdict === 'SUSPICIOUS');
  root.innerHTML = `<div class="gallery-page">
    <header class="topbar"><a class="brand" href="index.html">${ICONS.brand}LightAudit</a><span class="sep"></span>
      <span class="muted">Lighting-consistency audit of edited photos</span><span class="spacer"></span>
      <nav><button class="btn sm" type="button" data-upload aria-disabled="${!api}" title="${api ? 'Upload a photo and run a full audit on the server' : 'Needs the LightAudit server: python -m lightaudit.cli serve'}">${ICONS.upload}<span class="lbl">Audit your photo</span></button>
        <button class="btn ghost" id="help-btn">${ICONS.help}<span class="lbl">Help</span></button>${themeButton()}</nav></header>
    <main class="gallery-main">
      <section class="hero">
        <canvas class="hero-bg" id="hero-bg" aria-hidden="true"></canvas>
        <span class="hero-bg-cap mono" id="hero-bg-cap" aria-hidden="true"></span>
        <div class="hero-copy" data-hero>
          <h1>Checks whether one light explains every part of a photo, and shows the evidence</h1>
          <p class="lede">For each region of the image, LightAudit estimates which directions the light could come from, using shading, specular highlights and silhouettes. If one region's light disagrees with the light the other regions agree on, the region is flagged. When the photo carries too little lighting evidence it says so instead of guessing.</p>
          <div class="hero-actions">
            <button class="btn primary lg" type="button" data-upload aria-disabled="${!api}" title="${api ? 'Upload a photo and run a full audit on the server' : 'Needs the LightAudit server: python -m lightaudit.cli serve'}">${ICONS.upload}Audit your photo</button>
            ${featured ? `<a class="btn lg" href="?bundle=${encodeURIComponent(featured.name)}">Open the example audit</a>` : ''}
          </div>
          <p class="hero-note faint">${api ? 'JPEG or PNG. Mark the area to check, or let it find regions. About 5 minutes on a laptop CPU.' : 'Uploads need the LightAudit server: python -m lightaudit.cli serve'}</p>
          <div class="legend-verdicts">${chip('CONSISTENT')}${chip('SUSPICIOUS')}${chip('INSUFFICIENT')}${chip('CONFLICT')}</div>
        </div>
      </section>
      ${featured ? `<section class="example" data-reveal>
        <div class="section-head"><h2>A real audit</h2><span class="faint">${featured.name === 'real_mit_pear_spliced' ? 'Part of this object was pasted from a photo under another lamp. ' : ''}Open it to inspect every number</span></div>
        <a class="hero-visual" href="?bundle=${encodeURIComponent(featured.name)}" aria-label="Open the audit of ${esc(featured.title)}">
          <div class="hv-photo"><canvas id="hv-canvas" aria-hidden="true"></canvas><span class="hv-cap">${esc(featured.title)}</span></div>
          <div class="hv-card" id="hv-card"><div class="hv-loading faint">Loading the audit</div></div>
        </a>
      </section>` : ''}
      <section class="intro" data-reveal>
        <div><span class="micro">Every number is inspectable</span>
          <p>Drag your own light on the 3D dome, relight the photo, and see where the prediction does not fit. The attack lab then re-lights fakes to measure how easily a forger could pass.</p>
        </div>
        <div><span class="micro">What it does not claim</span>
          <ul>
            <li>${ICONS.cross}<span>It is not an AI-image detector. A picture generated in one pass usually has consistent lighting.</span></li>
            <li>${ICONS.cross}<span>A flag is not proof of fraud. A flag means <b>"send for human review"</b>, never "this is fraud".</span></li>
            <li>${ICONS.cross}<span>A careful forger who re-lights the edit can pass the shading check; the attack lab shows how much work that takes.</span></li>
            <li>${ICONS.info}<span>Results on synthetic scenes do not automatically transfer to real photos. The alert threshold holds only for photos like the calibration set.</span></li>
          </ul>
        </div>
      </section>
      <div class="section-head"><h2 class="micro">Audited images</h2><span class="faint">${index.length} bundle${index.length === 1 ? '' : 's'} · open one to inspect</span></div>
      <div class="cards">${cards}</div>
      <p class="gallery-foot">Synthetic scenes use simulated surface normals unless stated. ${esc(REVIEW)}</p>
    </main></div>`;
  root.querySelectorAll('[data-upload]').forEach((b) => b.addEventListener('click', () => { if (api) onUpload(); }));
  if (featured) heroPreview(root, featured);
  const cap = root.querySelector('#hero-bg-cap');
  asciiBackground(root.querySelector('#hero-bg'), {
    onLight: (az, el) => { cap.textContent = `one light · az ${Math.round(az)}° · el ${Math.round(el)}°`; },
  });
  galleryMotion(root);
}

// Motion on the gallery (anime.js and Lenis, vendored; both optional): the hero enters once, cards rise in as
// they scroll into view, and the page scrolls smoothly. Nothing moves when the viewer prefers reduced motion.
function galleryMotion(root) {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const anime = window.anime;
  if (reduce || !anime) return;
  document.documentElement.classList.add('js-motion');
  const ease = 'cubicBezier(.22, 1, .36, 1)';
  anime({ targets: root.querySelectorAll('[data-hero]'), opacity: [0, 1], translateY: [12, 0], duration: 600, easing: ease, delay: anime.stagger(120) });
  anime({ targets: '#hero-bg', opacity: [0, 1], duration: 1400, easing: 'linear' });
  const io = new IntersectionObserver((entries) => {
    const show = entries.filter((e) => e.isIntersecting).map((e) => e.target);
    if (!show.length) return;
    show.forEach((el) => io.unobserve(el));
    anime({ targets: show, opacity: [0, 1], translateY: [16, 0], duration: 520, easing: ease, delay: anime.stagger(50) });
  }, { rootMargin: '0px 0px -8% 0px' });
  root.querySelectorAll('[data-reveal]').forEach((el) => io.observe(el));
  if (window.Lenis) {
    const lenis = new window.Lenis({ lerp: 0.1, smoothWheel: true });
    const tick = (t) => { lenis.raf(t); requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  }
}

// Explanation from a stored manifest, with the current wording: per_region is matched to the regions by id.
function whyText(m) {
  const byId = new Map(m.regions.map((r) => [r.id, r]));
  const regs = m.fusion.per_region.map((p) => byId.get(p.id));
  const per = m.fusion.per_region.map((p, k) => ({ ...regs[k], ...p, index: k }));
  const idx = (ids) => (ids || []).map((id) => regs.findIndex((r) => r.id === id));  // bundles store region ids
  return explain({ ...m.fusion, per_region: per, flagged: idx(m.fusion.flagged), panel_flagged: idx(m.fusion.panel_flagged) }, regs)
    .split(' Please review')[0];
}

// The hero shows a real audit: the photo with its marked area outlined and the verdict from its own manifest.
async function heroPreview(root, b) {
  const base = `../bundles/${b.name}/`;
  const card = root.querySelector('#hv-card');
  try {
    const m = await (await fetch(base + 'manifest.json')).json();
    const f = m.fusion;
    const roi = m.regions.find((r) => r.name === 'ROI') || m.regions[f.top_region ?? 0];
    const pr = f.per_region.find((p) => p.flagged) || null;
    const meta = VERDICT_META[f.verdict] || { word: f.verdict, action: '' };
    const z = roi && roi.panel_z != null ? roi.panel_z : null;
    card.innerHTML = `<div class="hv-head v-${esc(f.verdict)}">${ICONS[f.verdict] || ''}<span>${esc(meta.word)}</span></div>
      <p class="hv-action">${esc(meta.action)}</p>
      ${z != null ? `<div class="hv-score"><span class="faint">Marked area vs its panel</span><span class="num"><span id="hv-z">0.0</span>× alert</span></div>
        <div class="gauge v-${esc(f.verdict)}"><i class="fill" id="hv-fill" style="width:0%"></i><i class="tau" style="left:${(100 / 3).toFixed(1)}%"></i></div>
        <div class="gauge-scale"><span>0</span><span>alert</span><span>3×</span></div>` : ''}
      <p class="hv-why">${richText(whyText(m))}</p>
      <div class="hv-meta mono faint">${esc(m.image.source)} photo · ${esc(m.normals_backend)} normals${pr ? ` · ${esc(m.regions[f.per_region.indexOf(pr)].name)} flagged` : ''}</div>`;
    if (z != null) {
      const fill = card.querySelector('#hv-fill'), out = card.querySelector('#hv-z');
      const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
      requestAnimationFrame(() => { fill.style.width = `${Math.min(100, z / 3 * 100).toFixed(1)}%`; });
      const t0 = performance.now();
      const step = (t) => {
        const k = reduce ? 1 : Math.min(1, (t - t0) / 700);
        out.textContent = (z * (1 - (1 - k) ** 3)).toFixed(1);
        if (k < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    }
    const [img, lab] = await Promise.all(['image.png', 'labels.png'].map((n) => new Promise((ok, bad) => {
      const im = new Image(); im.onload = () => ok(im); im.onerror = bad; im.src = base + n;
    })));
    const cv = root.querySelector('#hv-canvas');
    cv.width = img.width; cv.height = img.height;
    const ctx = cv.getContext('2d');
    ctx.drawImage(lab, 0, 0);
    const L = ctx.getImageData(0, 0, cv.width, cv.height).data;
    ctx.drawImage(img, 0, 0);
    if (roi) {  // outline the marked area: ROI pixels with a non-ROI neighbour
      const out = ctx.getImageData(0, 0, cv.width, cv.height);
      const W = cv.width, H = cv.height, id = roi.id;
      const col = getComputedStyle(document.documentElement).getPropertyValue('--bad').trim() || '#f0524f';
      const [cr, cg, cb] = [1, 3, 5].map((i) => parseInt(col.slice(i, i + 2), 16));
      for (let y = 2; y < H - 2; y++) for (let x = 2; x < W - 2; x++) {
        const k = y * W + x;
        if (L[k * 4] !== id) continue;
        if ([1, 2].some((d) => L[(k - d) * 4] !== id || L[(k + d) * 4] !== id || L[(k - d * W) * 4] !== id || L[(k + d * W) * 4] !== id)) {  // 2 px line
          out.data[k * 4] = cr; out.data[k * 4 + 1] = cg; out.data[k * 4 + 2] = cb;
        }
      }
      ctx.putImageData(out, 0, 0);
    }
    cv.classList.add('ready');
  } catch (e) {
    card.innerHTML = '<div class="hv-loading faint">Preview unavailable</div>';
  }
}

// ------------------------------------------------------------------ loading skeleton
export function skeletonHTML(name) {
  const bars = (ws) => ws.map((w) => `<div class="skel-bar" style="width:${w}%"></div>`).join('');
  return `<div class="app skel" aria-busy="true">
  <header class="topbar"><a class="brand" href="index.html">${ICONS.brand}LightAudit</a><span class="sep"></span>
    <div class="title"><h1 class="muted">${esc(name)}</h1></div><span class="spacer"></span><nav>${themeButton()}</nav></header>
  <div class="load-line" role="progressbar" aria-label="Loading the audit"><i id="lp"></i></div>
  <main class="workspace">
    <section class="panel" style="grid-area:verdict"><div class="skel-verdict"><div>${bars([30, 55, 70])}</div><div>${bars([20, 90, 80, 60])}</div></div></section>
    <section class="panel" style="grid-area:image"><div class="panel-head"><span class="micro">Image</span></div><div class="stage"></div></section>
    <section class="panel" style="grid-area:dome"><div class="panel-head"><span class="micro">Light dome</span></div><div class="stage"></div></section>
    <section class="panel" style="grid-area:table"><div class="panel-head"><span class="micro">Regions</span></div><div style="padding:16px;display:grid;gap:12px">${bars([100, 100, 100])}</div></section>
  </main></div>`;
}

// ------------------------------------------------------------------ main workspace skeleton
export function workspaceHTML(b) {
  const m = b.manifest;
  const modes = [['observed', 'Observed'], ['regions', 'Regions'], ['relit', 'Relit'], ['counterfactual', 'Counterfactual'], ['residual', 'Residual'], ['normals', 'Normals']];
  return `<div class="app">
  <header class="topbar">
    <a class="brand" href="index.html" title="Back to the gallery">${ICONS.brand}LightAudit</a><span class="sep"></span>
    <div class="title"><h1>${esc(m.title)}</h1><span id="head-chip"></span>
      <span class="tag" title="surface normals backend">${esc(m.normals_backend)}</span><span class="tag">${esc(m.image.source)}</span></div>
    <span class="spacer"></span>
    <nav aria-label="Views">
      <a class="btn ghost" href="index.html">${ICONS.grid}<span class="lbl">Gallery</span></a>
      <button class="btn ghost" id="explain-btn" title="How this verdict was made (E)">${ICONS.steps}<span class="lbl">Explain</span></button>
      <button class="btn ghost" id="attack-btn" title="Attack lab (A)">${ICONS.target}<span class="lbl">Attack lab</span></button>
      <button class="btn ghost" id="help-btn" title="Help (?)">${ICONS.help}<span class="lbl">Help</span></button>
      ${themeButton()}
    </nav>
  </header>
  <main class="workspace">
    <section class="panel" id="image-panel" aria-label="Image view">
      <div class="panel-head">
        <span class="micro">Image</span>
        <div class="seg" role="tablist" aria-label="Image mode" id="mode-tabs">${modes.map(([k, l], i) =>
          `<button role="tab" data-mode="${k}" aria-selected="false" title="${l} (${i + 1})">${l}<span class="k">${i + 1}</span></button>`).join('')}</div>
        <span class="spacer"></span>
        <span id="mode-tools"></span>
        <button class="btn ghost sm" id="split-btn" aria-pressed="false" aria-label="Split view" title="Split view: Observed | current mode">${ICONS.split}</button>
        <button class="btn ghost sm" id="shadow-btn" aria-pressed="false" aria-label="Shadow-pair tool (experimental)" title="Shadow-pair tool (experimental)">${ICONS.shadow}</button>
      </div>
      <div class="stage" id="image-stage"><canvas id="image-canvas" aria-label="Audited photo; click a region to select it"></canvas>
        <canvas class="overlay2d" id="image-overlay"></canvas><div class="tip" id="image-tip" role="tooltip"></div></div>
      <div class="panel-foot" id="image-foot"></div>
    </section>
    <section class="panel" id="dome-panel" aria-label="Light dome">
      <div class="panel-head">
        <span class="micro">Light dome</span>
        <label class="sr-only" for="shell-sel">Shell shows</label>
        <select class="sel" id="shell-sel" title="What the sphere shows">
          <option value="selected">Selected region's light map</option><option value="consensus">Consensus map</option>
          <option value="all">All regions overlay</option><option value="none">No map</option></select>
        <label class="check" title="68% (solid) and 95% (dashed) credible cones (C)"><input type="checkbox" id="cones-cb"> Cones</label>
        <span class="spacer"></span>
        <div class="seg" id="baseline-seg" role="group" aria-label="Light estimator" ${b.ls ? '' : 'hidden'}>
          <button data-b="rank" aria-pressed="true" title="The shading cue the audit used">Audit cue</button>
          <button data-b="ls" aria-pressed="false" title="The other shading cue (rank or least squares), for comparison only">Baseline cue</button></div>
      </div>
      <div class="stage" id="dome-stage"></div>
      <div class="panel-foot">
        <div class="sun" role="group" aria-label="Sun position: moves your light and relights the photo">
          <span class="readout"><span class="sw" aria-hidden="true"></span>Sun</span>
          <label title="Direction round the scene: 0 = from the camera side, +90 = from the right">Azimuth
            <input type="range" id="sun-az" min="-180" max="180" step="1" value="0"><output id="sun-az-o" for="sun-az">0°</output></label>
          <label title="Height above the horizon: 0 = grazing, 90 = straight above">Elevation
            <input type="range" id="sun-el" min="-10" max="90" step="1" value="45"><output id="sun-el-o" for="sun-el">45°</output></label>
          <button class="btn sm sweep" id="sun-sweep" type="button" aria-pressed="false" title="Swing the sun once round the scene and watch the relit photo">Sweep</button>
        </div>
        <span class="spacer"></span>
        <button class="btn ghost sm" id="snap-cons" title="Snap the sun to the direction the regions agree on">Consensus</button>
        <button class="btn ghost sm" id="snap-sel" title="Snap the sun to the selected region's own estimate">Selected</button>
      </div>
    </section>
    <section class="panel" id="verdict-panel" aria-label="Verdict">
      <div class="panel-head"><span class="micro">Verdict</span><span id="live-tag"></span><span class="spacer"></span>
        <button class="btn ghost sm" id="tune-btn" aria-expanded="false" title="Cue weights and thresholds">${ICONS.tune}Tune</button></div>
      <div class="verdict-body" id="verdict-body"></div>
    </section>
    <section class="panel" id="table-panel" aria-label="Regions">
      <div class="panel-head"><span class="micro">Regions</span><span class="faint" id="table-note"></span><span class="spacer"></span>
        <span class="faint" style="font-size:11px">click a row to select · checkbox = use in fusion</span></div>
      <div class="table-wrap"><table class="regions">
        <thead><tr>
          <th class="plain" scope="col"><span class="sr-only">Use</span>Use</th>
          <th scope="col" data-sort="name"><button>Region</button></th>
          <th scope="col" data-sort="weight"><button>Weight</button></th>
          <th scope="col" data-sort="shortfall"><button>Shortfall</button></th>
          <th scope="col" data-sort="angle"><button>Angle</button></th>
          <th scope="col" data-sort="like"><button title="agreement of each region with your light">At your light</button></th>
          <th class="plain" scope="col">Cues</th>
          <th scope="col" data-sort="status"><button>Status</button></th>
        </tr></thead><tbody id="region-rows"></tbody></table></div>
    </section>
  </main></div>`;
}
