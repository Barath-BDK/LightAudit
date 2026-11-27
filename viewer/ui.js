// DOM building blocks: icons, verdict chip/banner, region table, gallery, toasts, overlays.

import { VERDICT_META, REVIEW, esc, richText, reasonOf, whatIfText, CUE_NAMES, plainWhy, regionName } from './text.js';
import { azElDeg } from './grid.js';
import { initHero } from './plot.js';

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
// Main: the verdict word, one sentence, one action, Why. Extra (inside the Details disclosure): the numbers.
/** Steps of the rail's "What to try" path the user has already used. */
export const TRIED = new Set();

export function renderVerdict(el, { fusion, regions, tau, whatIf, light, modified, original, display }) {
  const v = fusion.verdict;
  const m = VERDICT_META[v] || { word: v, action: '' };
  const s = fusion.n_reliable ? fusion.S_img : null;
  const [az, elv] = azElDeg(light);
  const why = fusion.text.split(' Please review manually.')[0];
  el.innerHTML = `
    <div class="v-word v-${v}" aria-live="polite">${esc(m.word)}</div>
    <p class="why">${esc(plainWhy(fusion, regions))}</p>
    <button type="button" class="btn primary pill" id="review-btn">${v === 'SUSPICIOUS' ? 'Send for human review' : 'Record review'}</button>
    <h2 class="v-h">What to try</h2>
    <ol class="path">${[['sun', ICONS.sun, 'Drag the sun', 'On the sky map'],
      ['relit', ICONS.split, 'Compare Relit', 'The photo under your sun'],
      ['details', ICONS.info, 'Open details', 'Region by region']].map(([k, ic, l, sub]) =>
      `<li><button type="button" class="path-go${TRIED.has(k) ? ' done' : ''}" data-go="${k}"><span class="path-ic">${TRIED.has(k) ? ICONS.check : ic}</span>
        <span class="path-l">${l}<small>${sub}</small></span><span class="path-chev" aria-hidden="true"></span></button></li>`).join('')}
    </ol>`;
  const extra = document.getElementById('verdict-extra');
  if (!extra) return;
  const pct = (x) => Math.max(0, Math.min(100, x / 6.91 * 100)).toFixed(1);
  const rows = regions.map((r, i) => {
    const p = fusion.per_region[i], d = display ? display[i] : p;
    const st = p.excluded ? ['Left out', 'na', r.reason || 'excluded'] : !p.reliable ? ['Not assessed', 'na', reasonOf(r)]
      : p.flagged ? ['Flagged', 'SUSPICIOUS', ''] : ['Agrees', 'CONSISTENT', ''];
    const off = p.reliable && d && d.angle_deg != null ? `${d.angle_deg.toFixed(0)}° off the shared light` : st[2];
    return `<li><button type="button" class="reg" data-sel="${i}"><span class="swatch" style="background:${esc(r.color)}"></span>
      <span class="reg-n">${esc(regionName(r.name))}</span><span class="reg-s v-${st[1]}">${st[0]}</span><span class="reg-d">${esc(off)}</span></button></li>`;
  }).join('');
  extra.innerHTML = `
    <section class="dgroup"><h3>What we measured</h3>
      <p class="dlead">${esc(m.action)}</p>
      <p class="dtext">Image score ${s === null ? 'not available' : `<b>${s.toFixed(2)}</b>`} against an alert level of <b>${tau.toFixed(2)}</b>. Lower is better: 0 means every region agrees.</p>
      ${s === null ? '' : `<div class="meter-line" aria-hidden="true"><i style="width:${pct(s)}%"></i><b style="left:${pct(tau)}%"></b></div>`}
      <p class="dtext">${richText(why)}</p>
      <p class="dtext faint">${esc(REVIEW)}${original && modified ? ` The exported verdict for this photo is ${esc((VERDICT_META[original] || { word: original }).word)}.` : ''}</p>
      <p class="dtext faint">At your light (azimuth ${az.toFixed(0)}°, elevation ${elv.toFixed(0)}°): ${whatIf ? esc(whatIfText(whatIf, regions)) : 'no result'}.</p>
    </section>
    <section class="dgroup"><h3>Each region</h3>
      <p class="dtext faint">${fusion.n_reliable} of ${regions.length} regions could be assessed. Select one to see its light on the dome.</p>
      <ul class="reg-list">${rows}</ul>
    </section>`;
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

// ------------------------------------------------------------------ landing (gallery)
const HERO = 'real_mit_pear_spliced';
const CLAIM = 'real_street_car';

// index titles for the outdoor photos are file names ("street_car.jpg"): show them as words
function nice(t) { return /\.(jpe?g|png)$/i.test(t) ? (t = t.replace(/\.(jpe?g|png)$/i, '').replace(/_/g, ' '), t.charAt(0).toUpperCase() + t.slice(1)) : t; }
function srcLabel(b) { return b.source === 'real' ? 'Real photo' : 'Synthetic'; }
function verdictWord(v) { return esc((VERDICT_META[v] || { word: v }).word); }

export function renderGallery(root, { index, api, onUpload }) {
  const has = (n) => index.some((b) => b.name === n);
  const hero = has(HERO) ? HERO : null;
  const claim = index.find((b) => b.name === CLAIM);
  const clean = index.find((b) => b.name === 'real_mit_pear_clean');
  const uploadTitle = api ? 'Upload a photo and run a full audit on the server' : 'Needs the LightAudit server: python -m lightaudit.cli serve';
  const tiles = [...index].sort((a, b) => (b.source === 'real') - (a.source === 'real')).map((b) => `<a class="tile" href="?bundle=${encodeURIComponent(b.name)}">
      <span class="tile-img"><img src="../bundles/${esc(b.thumb || `${b.name}/thumb.jpg`)}" alt="" width="320" height="220"></span>
      <span class="tile-title">${esc(nice(b.title))}</span>
      <span class="tile-meta"><span>${srcLabel(b)}</span><span class="v-${esc(b.verdict)}">${verdictWord(b.verdict)}</span></span></a>`).join('');
  const base = `../bundles/${HERO}/`;
  root.innerHTML = `<div class="landing">
    <header class="topbar"><div class="topbar-in">
      <a class="brand" href="index.html">${ICONS.brand}<span>LightAudit</span></a><span class="spacer"></span>
      <nav aria-label="Site"><a class="nav-link" href="#how">How it works</a><a class="nav-link" href="#photos">Photos</a>
        <button class="nav-link" type="button" id="help-btn">Help</button>${themeButton()}</nav></div></header>
    <main>
      <section class="hero" aria-labelledby="hero-h">
        <h1 id="hero-h">Every claim photo has one sun.</h1>
        <p class="hero-lede">LightAudit finds the part that was lit by another. Drag the sun to see it.</p>
        <div class="hero-actions">
          <button class="pill" type="button" data-upload aria-disabled="${!api}" title="${uploadTitle}">Audit a claim photo</button>
          ${hero ? `<a class="text-link" href="?bundle=${HERO}">Open the case</a>` : ''}
        </div>
        ${hero ? `<div class="hero-stage" id="hero-stage">
          <canvas id="hv-canvas" aria-hidden="true"></canvas>
          <svg id="hero-svg" aria-hidden="false"></svg>
          <p class="hero-live" id="hero-live" aria-live="polite">Loading the real photo</p>
        </div>
        <p class="hero-cap">Real photo from the MIT Intrinsic Images dataset. The outlined patch was pasted in from a shot under a different lamp.</p>` : ''}
      </section>

      ${claim ? `<section class="band alt stack" aria-labelledby="claims-h">
        <div class="band-copy"><h2 id="claims-h">Made for claim photos.</h2>
          <p>A claims reviewer uploads a vehicle-damage photo, marks the damage and reads one verdict: does a single light explain the whole picture? If a region was lit by a different sun, the claim goes to a person.</p></div>
        <figure class="band-figure"><img src="../bundles/${CLAIM}/image.png" alt="${esc(nice(claim.title))}" width="1024" height="657">
          <figcaption>${esc(nice(claim.title))}. Real photo, Wikimedia Commons. Verdict: <span class="v-${esc(claim.verdict)}">${verdictWord(claim.verdict)}</span>.</figcaption></figure>
      </section>` : ''}

      ${hero ? `<section class="band" id="how" aria-labelledby="how-h">
        <div class="band-copy centered"><h2 id="how-h">How it works.</h2></div>
        <ol class="steps-row">
          <li><img src="${base}image.png" alt="The pear photo" loading="lazy" width="568" height="668"><h3>Mark the damage</h3><p>Outline the area you want checked. The rest of the photo becomes the reference.</p></li>
          <li><img src="${base}counterfactual.png" alt="The pear re-shaded under the light its regions agree on" loading="lazy" width="568" height="668"><h3>Measure the light</h3><p>For each region, LightAudit estimates which way its surfaces face and where its light comes from, then re-shades the photo under the light they share.</p></li>
          <li><img src="${base}heat.png" alt="Residual map: where the shading does not fit" loading="lazy" width="568" height="668"><h3>Compare</h3><p>If one sun explains every region, the photo passes. A region that needs a different sun is flagged.</p></li>
        </ol>
      </section>` : ''}

      <section class="band alt" aria-labelledby="bench-h">
        <div class="band-copy"><h2 id="bench-h">Measured on real photos.</h2>
          <p>We tested the marked-area check on 10 held-out real tabletop objects: 400 clean areas and 400 pasted ones. It raised a false alarm on 5.2% of the clean areas and caught 45% of the pasted ones.</p>
          <p>When the pasted light came from 80° or more away, it caught 57%. After the forger matched colours, 32%.</p>
          <p class="quiet">These are tabletop objects, not cars. No real car photos with real or pasted damage have been tested yet.</p></div>
        <figure class="bars" aria-label="Real marked-area benchmark">
          ${[['False alarms on clean areas', 5.2], ['Pasted areas caught', 45], ['Caught, light 80° or more away', 57], ['Caught, after colour matching', 32]]
            .map(([l, v]) => `<div class="bar-row"><span class="bar-l">${l}</span><span class="bar-t"><i style="width:${v}%"></i></span><span class="bar-v">${v}%</span></div>`).join('')}
        </figure>
      </section>

      <section class="band stack" aria-labelledby="limits-h">
        <div class="band-copy"><h2 id="limits-h">A flag means send for human review. Never fraud.</h2>
          <p>LightAudit is not an AI-image detector: a picture generated in one pass usually has consistent light. A careful forger who re-lights the edit can pass the shading check, and the attack lab shows how much work that takes. When a photo carries too little lighting evidence, it says so instead of guessing.</p></div>
        ${clean && hero ? `<div class="pair">
          <a href="?bundle=real_mit_pear_clean"><img src="../bundles/real_mit_pear_clean/thumb.jpg" alt="Real pear photo, unedited" loading="lazy"><span>Unedited <b class="v-${esc(clean.verdict)}">${verdictWord(clean.verdict)}</b></span></a>
          <a href="?bundle=${HERO}"><img src="../bundles/${HERO}/thumb.jpg" alt="Real pear photo with a pasted patch" loading="lazy"><span>Pasted patch <b class="v-SUSPICIOUS">${verdictWord('SUSPICIOUS')}</b></span></a>
        </div>` : ''}
      </section>

      <section class="band alt photos" id="photos" aria-labelledby="photos-h">
        <div class="band-copy"><h2 id="photos-h">Audited photos.</h2>
          <p>${index.filter((b) => b.source === 'real').length} real photos and ${index.filter((b) => b.source !== 'real').length} synthetic scenes. Open any one to inspect its light.</p></div>
        <div class="tiles">${tiles}</div>
      </section>
    </main>
    <footer class="foot"><p>Outdoor car photos: Wikimedia Commons, CC BY / CC BY-SA. Tabletop objects: MIT Intrinsic Images. Synthetic scenes use simulated surface normals.</p>
      <p>${esc(REVIEW)}</p></footer>
  </div>`;
  root.querySelectorAll('[data-upload]').forEach((b) => b.addEventListener('click', () => { if (api) onUpload(); else toast(uploadTitle, 'info'); }));
  if (hero) initHero(root.querySelector('#hero-stage'), root.querySelector('#hero-live'), base);
}

// ------------------------------------------------------------------ loading skeleton
function topbar(title, navInner) {
  return `<header class="topbar"><div class="topbar-in">
    <a class="brand" href="index.html" title="All photos">${ICONS.brand}<span>LightAudit</span></a>
    ${title ? `<h1 class="topbar-title">${esc(title)}</h1>` : ''}<span class="spacer"></span>
    <nav aria-label="Views">${navInner}${themeButton()}</nav></div></header>`;
}

export function skeletonHTML(name) {
  return `<div class="app skel" aria-busy="true">${topbar(name, '')}
  <div class="load-line" role="progressbar" aria-label="Loading the audit"><i id="lp"></i></div>
  <main class="workspace"><aside class="rail"></aside><section class="center"><div class="stage"></div></section><section class="side"><div class="stage"></div></section></main></div>`;
}

// ------------------------------------------------------------------ main workspace
export function workspaceHTML(b) {
  const m = b.manifest;
  const more = [['regions', 'Regions'], ['counterfactual', 'Counterfactual'], ['normals', 'Normals']];
  return `<div class="app">
  ${topbar(nice(m.title), `<a class="nav-link" href="index.html">Photos</a>
      <button class="nav-link" id="explain-btn" title="How this verdict was made (E)">Explain</button>
      <button class="nav-link" id="attack-btn" title="Attack lab (A)">Attack lab</button>
      <button class="nav-link" id="help-btn" title="Help (?)">Help</button>`)}
  <main class="workspace">
    <aside class="rail" id="verdict-panel" aria-label="Verdict">
      <div class="rail-in">
        <div id="verdict-body"></div>
        <div id="live-tag"></div>
        <details class="disclosure" id="details">
          <summary>Details</summary>
          <div class="disclosure-body">
            <div id="verdict-extra"></div>
            <details class="subdisclosure" id="numbers"><summary>Show numbers</summary>
            <section id="table-panel" aria-label="Region numbers">
              <p class="dtext faint">Untick a region to leave it out of the fusion. <span id="table-note"></span></p>
              <div class="table-wrap"><table class="regions">
                <thead class="sr-only"><tr>
                  <th class="plain" scope="col">Use</th>
                  <th scope="col" data-sort="name"><button>Region</button></th>
                  <th scope="col" data-sort="weight"><button>Weight</button></th>
                  <th scope="col" data-sort="shortfall"><button>Shortfall</button></th>
                  <th scope="col" data-sort="angle"><button>Angle</button></th>
                  <th scope="col" data-sort="like"><button>At your light</button></th>
                  <th class="plain" scope="col">Cues</th>
                  <th scope="col" data-sort="status"><button>Status</button></th>
                </tr></thead><tbody id="region-rows"></tbody></table></div>
            </section></details>
            <section class="dgroup tune-group"><h3>Tune</h3>
              <p class="dtext faint">Change the cue weights and the alert level. The verdict recomputes live, and Reset returns to the calibrated values.</p>
              <button class="btn" id="tune-btn" aria-expanded="false" title="Cue weights and thresholds">${ICONS.tune}Open tuning</button>
              <p class="dtext faint">${m.image.source === 'real' ? 'Real photo' : 'Synthetic scene'}. Surface directions from ${esc(m.normals_backend)}.</p>
            </section>
          </div>
        </details>
      </div>
    </aside>
    <section class="center" id="image-panel" aria-label="Photo">
      <div class="stage-frame"><div class="stage" id="image-stage" style="--ar:${b.W} / ${b.H}"><canvas id="image-canvas" aria-label="Audited photo; click a region to select it"></canvas>
        <canvas class="overlay2d" id="image-overlay"></canvas><div class="tip" id="image-tip" role="tooltip"></div><div class="result-card" id="result-card" aria-live="polite"></div></div></div>
      <div class="toolbar">
        <div class="segmented" role="tablist" aria-label="Photo evidence">${[['observed', 'Observed'], ['relit', 'Relit'], ['residual', 'Residual']].map(([k, l]) => `<button class="evidence-tab" role="tab" data-mode="${k}" aria-selected="false">${l}</button>`).join('')}</div>
        <span id="mode-tools"></span>
        <details class="menu more-evidence"><summary>More</summary>
          <div class="menu-body">
            <div class="seg" role="tablist" aria-label="More photo evidence" id="mode-tabs">${more.map(([k, l]) => `<button role="tab" data-mode="${k}" aria-selected="false">${l}</button>`).join('')}</div>
            <button class="btn sm" id="split-btn" aria-pressed="false" title="Split view: Observed beside the current mode">${ICONS.split}Split view</button>
            <button class="btn sm" id="shadow-btn" aria-pressed="false" title="Shadow-pair tool (experimental)">${ICONS.shadow}Shadow pairs</button>
          </div></details>
      </div>
      <p class="caption" id="image-foot"></p>
    </section>
    <section class="side" id="dome-panel" aria-label="Light dome">
      <button type="button" class="light-toggle" id="light-toggle" aria-expanded="false" aria-controls="side-body">Where the light comes from</button>
      <div class="side-body" id="side-body">
      <div class="stage" id="dome-stage">
        <details class="menu dome-menu"><summary>View</summary>
          <div class="menu-body">
            <label class="small" for="shell-sel">Sphere shows</label>
            <select class="sel" id="shell-sel">
              <option value="selected">Selected region's light map</option><option value="consensus">Consensus map</option>
              <option value="all">All regions overlay</option><option value="none">No map</option></select>
            <label class="check" title="68% (solid) and 95% (dashed) credible cones (C)"><input type="checkbox" id="cones-cb"> Cones</label>
            <div class="seg" id="baseline-seg" role="group" aria-label="Light estimator" ${b.ls ? '' : 'hidden'}>
              <button data-b="rank" aria-pressed="true" title="The shading cue the audit used">Audit cue</button>
              <button data-b="ls" aria-pressed="false" title="The other shading cue, for comparison only">Baseline cue</button></div>
          </div></details>
      </div>
      <div class="sky-dock">
        <div class="sky" id="sky" role="group" aria-label="Sky map: drag the sun to relight the photo">
          <svg id="sky-svg" viewBox="-120 -120 240 240" aria-hidden="true"></svg>
        </div>
        <div class="sky-side">
          <div class="sky-read"><span>Azimuth</span><output id="sun-az-o">0°</output></div>
          <div class="sky-read"><span>Elevation</span><output id="sun-el-o">45°</output></div>
          <input type="range" id="sun-az" min="-180" max="180" step="1" value="0" aria-label="Sun azimuth">
          <input type="range" id="sun-el" min="-10" max="90" step="1" value="45" aria-label="Sun elevation">
          <div class="sky-legend"><span><i class="k-sun"></i>Your sun</span><span><i class="k-cons"></i>Consensus</span><span><i class="k-reg"></i>Region estimates</span></div>
          <div class="sky-actions">
            <button class="btn sm" id="sun-sweep" type="button" aria-pressed="false" title="Swing the sun once round the scene">Sweep</button>
            <button class="btn ghost sm" id="snap-cons" title="Snap the sun to the direction the regions agree on">Consensus</button>
            <button class="btn ghost sm" id="snap-sel" title="Snap the sun to the selected region's own estimate">Selected</button>
          </div>
        </div>
      </div>
      </div>
    </section>
  </main></div>`;
}
