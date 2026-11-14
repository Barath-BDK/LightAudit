// Explain stepper "How this verdict was made" (BUILD_SPEC 12.6) and the Help panel (12.8).

import { openDialog, chip, ICONS, $, $$ } from './ui.js';
import { esc, richText, reasonOf, VERDICT_META, REVIEW } from './text.js';
import { Dome } from './dome.js';
import { azElDeg, dir } from './grid.js';

const FIG = '../docs/figures/';

export const LIMITATIONS = '<strong>What LightAudit can and cannot do.</strong> LightAudit checks whether the lighting of different parts of a photo is physically consistent. It does <strong>not</strong> detect AI-generated images in general: a generator that produces the whole picture in one pass usually gives every object the same plausible light. A careful forger who re-lights an edited region to match the scene can pass the shading check (the attack lab measures exactly how much extra work that takes). Real photos can be flagged wrongly when they contain several lights, strong reflections, or bad surface-direction estimates, and many real photos (overcast, indoor, heavily filtered, tiny or flat objects) carry too little lighting evidence, in which case LightAudit says "insufficient evidence". Surface directions come from pretrained neural networks and are learned guesses, not measurements. The alert threshold controls the false-alarm rate only for photos like those used for calibration. <strong>A flag means "send for human review", never "this is fraud".</strong> Results on synthetic scenes do not automatically transfer to real photos; real-photo results are qualitative unless stated.';

function hexRgb(h) { const n = parseInt(h.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }

const INFERNO = [[0, 0, 4], [50, 10, 94], [120, 28, 109], [188, 55, 84], [237, 105, 37], [251, 182, 26], [252, 255, 164]];
function inferno(t) {
  t = Math.max(0, Math.min(1, t)) * (INFERNO.length - 1);
  const i = Math.min(Math.floor(t), INFERNO.length - 2), f = t - i;
  return INFERNO[i].map((a, k) => a + (INFERNO[i + 1][k] - a) * f);
}

/** Renders one image layer of the bundle into an ImageData. kind: photo | regions | normals | unc | valid | heat */
function layer(B, kind, sel = -1) {
  const { W, H } = B, out = new ImageData(W, H), o = out.data, im = B.images.image.data, lab = B.lab;
  const colors = new Map(B.regions.map((r) => [r.id, hexRgb(r.color)]));
  const excl = new Set(B.regions.filter((r) => r.excluded).map((r) => r.id));
  for (let p = 0; p < W * H; p++) {
    let c = [im[4 * p], im[4 * p + 1], im[4 * p + 2]];
    const grey = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
    const id = lab[p];
    if (kind === 'regions' && id) {
      const col = colors.get(id) || [128, 128, 128];
      const a = excl.has(id) ? 0.2 : 0.5;
      c = c.map((x, k) => x * (1 - a) + col[k] * a);
      const x = p % W, y = (p / W) | 0;
      const edge = (x > 0 && lab[p - 1] !== id) || (x < W - 1 && lab[p + 1] !== id) || (y > 0 && lab[p - W] !== id) || (y < H - 1 && lab[p + W] !== id);
      if (edge) c = id === sel ? [255, 138, 61] : col;
    } else if (kind === 'normals' && B.images.normals) {
      const n = B.images.normals.data; c = [n[4 * p], n[4 * p + 1], n[4 * p + 2]];
      if (!id) c = c.map((x) => x * 0.25 + grey * 0.1);
    } else if (kind === 'unc' && B.images.unc) {
      c = inferno(B.images.unc.data[4 * p] / 255 * 45 / 35);
      if (!id) c = c.map((x) => x * 0.3);
    } else if (kind === 'valid' && B.images.valid) {
      const v = B.images.valid.data[4 * p] > 127;
      c = v ? [grey * 0.6 + 100, grey * 0.6 + 100, grey * 0.6 + 100] : [grey * 0.2, grey * 0.2, grey * 0.25];
      if (v) { c[1] += 40; }
    } else if (kind === 'heat' && B.images.heat) {
      const h = B.images.heat.data[4 * p] / 255;
      c = id && !excl.has(id) ? inferno(h) : [grey * 0.3, grey * 0.3, grey * 0.3];
    }
    o[4 * p] = c[0]; o[4 * p + 1] = c[1]; o[4 * p + 2] = c[2]; o[4 * p + 3] = 255;
  }
  return out;
}

function drawFit(canvas, img) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = Math.max(1, canvas.clientWidth * dpr), h = Math.max(1, canvas.clientHeight * dpr);
  canvas.width = w; canvas.height = h;
  const g = canvas.getContext('2d');
  const tmp = document.createElement('canvas');
  tmp.width = img.width; tmp.height = img.height;
  tmp.getContext('2d').putImageData(img, 0, 0);
  const s = Math.min((w - 20 * dpr) / img.width, (h - 20 * dpr) / img.height);
  g.imageSmoothingEnabled = s < 2;
  g.drawImage(tmp, (w - img.width * s) / 2, (h - img.height * s) / 2, img.width * s, img.height * s);
}

/** Scatter of Y against n.l at the region's reference light, with the fitted monotone curve g_k. */
function drawFitPlot(canvas, B, k, ref) {
  const r = B.regions[k];
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = canvas.clientWidth * dpr, h = canvas.clientHeight * dpr;
  canvas.width = w; canvas.height = h;
  const g = canvas.getContext('2d');
  const cs = getComputedStyle(document.documentElement);
  const text = cs.getPropertyValue('--text-2').trim(), line = cs.getPropertyValue('--line-2').trim();
  const L = 46 * dpr, R = 14 * dpr, T = 14 * dpr, Bm = 30 * dpr;
  const X = (s) => L + s * (w - L - R), Yp = (y) => h - Bm - y * (h - T - Bm);
  g.strokeStyle = line; g.lineWidth = dpr;
  g.strokeRect(L, T, w - L - R, h - T - Bm);
  g.fillStyle = text; g.font = `${11 * dpr}px system-ui, sans-serif`;
  g.fillText('n · l (at the reference light)', L + 4 * dpr, h - 9 * dpr);
  g.save(); g.translate(13 * dpr, T + 60 * dpr); g.rotate(-Math.PI / 2); g.fillText('luminance Y', 0, 0); g.restore();
  for (const t of [0, 0.5, 1]) { g.fillText(t.toFixed(1), X(t) - 6 * dpr, h - Bm + 13 * dpr); g.fillText(t.toFixed(1), L - 26 * dpr, Yp(t) + 4 * dpr); }
  if (!B.images.normals || !B.images.valid) return;
  const nd = B.images.normals.data, vd = B.images.valid.data;
  const col = r.color;
  g.fillStyle = col; g.globalAlpha = 0.35;
  let cnt = 0;
  const step = Math.max(1, Math.floor(r.area_px / 2500));
  for (let p = 0, seen = 0; p < B.W * B.H; p++) {
    if (B.lab[p] !== r.id || vd[4 * p] < 128) continue;
    if ((seen++ % step) !== 0) continue;
    let n = [nd[4 * p] / 127.5 - 1, nd[4 * p + 1] / 127.5 - 1, nd[4 * p + 2] / 127.5 - 1];
    const ln = Math.hypot(...n) || 1;
    const s = Math.max(0, (n[0] * ref[0] + n[1] * ref[1] + n[2] * ref[2]) / ln);
    g.fillRect(X(s) - dpr, Yp(B.Y[p]) - dpr, 2 * dpr, 2 * dpr);
    cnt++;
  }
  g.globalAlpha = 1;
  if (r.g_lut) {
    g.strokeStyle = cs.getPropertyValue('--text').trim(); g.lineWidth = 2 * dpr;
    g.beginPath();
    r.g_lut.forEach((y, i) => (i ? g.lineTo(X(i / 32), Yp(y)) : g.moveTo(X(i / 32), Yp(y))));
    g.stroke();
  }
  g.fillStyle = text;
  g.fillText(`${r.name}: ${cnt} usable pixels · curve = fitted monotone tone curve ĝ`, L + 6 * dpr, T + 14 * dpr);
}

function figure(name, caption) {
  return `<figure class="concept"><button type="button" data-zoom="${FIG}${name}" aria-label="Enlarge figure: ${esc(caption)}">
    <img src="${FIG}${name}" alt="${esc(caption)}" loading="lazy"></button><figcaption>${esc(caption)}</figcaption></figure>`;
}

export function openExplain(ctx) {
  const { B, state, allRegions } = ctx;
  const f = state.fusion, regs = allRegions();
  const m = B.manifest;
  let step = 0, dome = null, uncOn = false;
  let sel = state.selected ?? f.top_region ?? 0;
  const reliable = f.per_region.filter((p) => p.reliable).map((p) => p.index);
  const c = f.consensus;
  const nExcl = f.per_region.filter((p) => p.excluded).length;
  const nUnrel = f.per_region.filter((p) => !p.reliable && !p.excluded).length;
  const ef = ctx.exportFusion;
  const refOf = (k) => (!ef.consensus ? B.regions[k].center : ef.per_region[k].flagged ? dir(ef.per_region[k].ref_index) : ef.consensus.dir);

  const STEPS = [
    { title: 'The photo', vis: 'photo',
      text: () => `<p>This is the image being audited (${B.W} × ${B.H} px, ${esc(m.image.source)}). LightAudit asks one physical question: <em>can a single distant light explain the shading of every part of this photo?</em></p>
        <p class="small">It does not look at noise, compression or metadata. A pasted object lit from somewhere else breaks the one-light hypothesis; a fully generated image usually does not.</p>`,
      fig: () => figure('pipeline.svg', 'The pipeline: regions, normals, cues, light maps, fusion, verdict.') },
    { title: 'Split it into regions', vis: 'regions',
      text: () => `<p>The photo is divided into ${B.regions.length} regions (backend: <span class="mono">${esc(m.regions_backend)}</span>). Each region is assumed to have one material, so its brightness depends only on how it faces the light.</p>
        <p class="small">${nExcl} region(s) are excluded up front (sky, glass, tyres, too small) and shown hatched in the viewer. You can toggle any region in the table; the verdict is recomputed live.</p>`,
      fig: () => '' },
    { title: 'Estimate which way each surface faces', vis: 'normals', tools: true,
      text: () => `<p>Every pixel gets a surface direction (a <em>normal</em>, shown as colour: red = right, green = up, blue = toward you). Source: <span class="mono">${esc(m.normals_backend)}</span>.</p>
        <p class="small">These are estimates, never measurements. The uncertainty map (toggle above the image) shows where they are least trusted; uncertain pixels count less.</p>`,
      fig: () => '' },
    { title: 'Keep only usable pixels', vis: 'valid',
      text: () => `<p>Highlighted pixels are the ones the shading cue uses: inside the region (eroded away from its edges), neither blown out nor in deep shadow, facing the camera, with trustworthy normals.</p>
        <p class="small">Saturated pixels are not wasted: on glossy paint they become the specular-highlight cue. A region with fewer than 150 usable pixels gets no say.</p>`,
      fig: () => '' },
    { title: 'Each region votes for light directions', vis: 'dome-region', side: true,
      text: () => {
        const r = B.regions[sel], p = f.per_region[sel];
        const [az, el] = azElDeg(r.center);
        return `<p>For each candidate direction on the sphere, LightAudit asks: if the light came from here, would the brighter pixels be the ones facing it? It uses only the <em>ranking</em> of brightness, so any camera tone curve, exposure or colour grading leaves the answer unchanged.</p>
        <p class="small">The dome shows the light map of <b>${esc(r.name)}</b>${p.reliable ? `: it points to about az ${az.toFixed(0)}°, el ${el.toFixed(0)}° (68% cone ${r.r68_deg.toFixed(0)}°)` : ` (not reliable: ${esc(reasonOf(r))})`}. Below: brightness against n·l with the fitted monotone curve.</p>
        <label class="check">Region <select class="sel" id="ex-sel">${B.regions.map((x, i) => `<option value="${i}" ${i === sel ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select></label>`;
      },
      fig: () => figure('rank_invariance.svg', 'Ranking makes the estimate immune to the tone curve.') + figure('cue_geometry.svg', 'Extra cues: highlight mirror geometry, silhouette normals, shadow lines.') },
    { title: 'Do the light maps overlap?', vis: 'dome-all',
      text: () => {
        const rows = reliable.map((k) => ({ k, s: Math.max(0, state.display[k].shortfall ?? 0) }));
        return `<p>The ${reliable.length} reliable regions are combined (weighted by reliability) into a consensus light${c ? ` at about az ${c.az_deg.toFixed(0)}°, el ${c.el_deg.toFixed(0)}° (white ring and sun)` : ''}. Then each region is left out in turn: its <em>shortfall</em> says how badly it fits the light the others agree on (0 = perfect, 6.9 = no overlap).</p>
        <div class="sf-list" aria-label="Shortfall per region">${rows.map(({ k, s }) => `<div class="sf-row"><span class="n"><span class="swatch" style="background:${esc(regs[k].color)}"></span>${esc(regs[k].name)}</span>
          <span class="bar sf ${s > f.tau ? 'over' : ''}"><i style="width:${Math.min(100, s / 6.91 * 100)}%"></i><span class="alert" style="left:${f.tau / 6.91 * 100}%"></span></span><span class="num">${s.toFixed(2)}</span></div>`).join('') || '<p class="small">No reliable regions.</p>'}</div>
        <p class="small">The vertical tick is the calibrated alert level (${f.tau.toFixed(2)}). ${nUnrel} region(s) could not be assessed and are never flagged.</p>`;
      },
      fig: () => figure('shortfall_diagram.svg', 'Leave-one-out consensus and shortfall.') },
    { title: 'Where does it not fit?', vis: 'heat',
      text: () => `<p>Under the consensus light, each region's fitted tone curve predicts how bright every pixel should be. The heat map shows the mismatch in units of the expected noise: bright = does not fit.</p>
        <div style="display:flex;gap:10px;align-items:center">${chip(f.verdict)}<span class="muted">${esc(VERDICT_META[f.verdict].action)}</span></div>
        <p>${richText(f.text)}</p>${f.text.includes(REVIEW) ? '' : `<p class="small">${esc(REVIEW)}</p>`}`,
      fig: () => figure('triage.svg', 'The four verdicts and what to do with each.') + figure('conformal.svg', 'How the alert level is calibrated.') },
  ];

  const d = openDialog({ title: 'How this verdict was made', head: `<div class="steps" role="tablist" aria-label="Steps">${STEPS.map((s, i) =>
    `${i ? '<span class="ln"></span>' : ''}<button role="tab" data-step="${i}" title="${esc(s.title)}">${i + 1}</button>`).join('')}</div>`,
  foot: '<span class="faint">Use ← → to move between steps, Esc to close.</span><span class="spacer"></span><button class="btn" id="ex-prev">Previous</button><button class="btn accent" id="ex-next">Next</button>',
  onClose: () => { if (dome) dome.destroy(); document.removeEventListener('keydown', key, true); } });

  d.body.innerHTML = `<div class="explain-grid"><div class="explain-visual"><div class="vis-main" id="ex-main"></div><div class="vis-side" id="ex-side" hidden><canvas></canvas></div></div>
    <div class="explain-text" id="ex-text"></div></div>`;

  function render() {
    const s = STEPS[step];
    $$('.steps button', d.el).forEach((b, i) => { b.setAttribute('aria-current', i === step ? 'step' : 'false'); b.classList.toggle('done', i < step); });
    $('#ex-prev', d.el).disabled = step === 0;
    $('#ex-next', d.el).textContent = step === STEPS.length - 1 ? 'Close' : 'Next';
    $('#ex-text', d.el).innerHTML = `<span class="micro kicker">Step ${step + 1} of ${STEPS.length}</span><h3>${esc(s.title)}</h3>${s.text()}${s.fig()}`;
    const main = $('#ex-main', d.el), side = $('#ex-side', d.el);
    const isDome = s.vis.startsWith('dome');
    if (!isDome && dome) { dome.destroy(); dome = null; }
    if (isDome) {
      if (!dome) {
        main.innerHTML = '';
        dome = new Dome(main, { draggable: false, labels: true });
        dome.setPhoto(B.images.image.bitmap, B.W, B.H);
        dome.applyTheme();
      }
      if (s.vis === 'dome-region') {
        const r = B.regions[sel];
        dome.setShell('map', state.maps[sel]);
        dome.setCones(r.r68_deg < 179 ? [{ center: r.center, r68: r.r68_deg, r95: r.r95_deg, color: r.color, selected: true }] : [], null);
      } else {
        dome.setShell('overlay', null, reliable.map((k) => ({ A: state.maps[k], color: regs[k].color })));
        dome.setCones(reliable.map((k) => ({ center: regs[k].center, r68: regs[k].r68_deg, r95: regs[k].r95_deg, color: regs[k].color, flagged: f.per_region[k].flagged })),
          c ? { dir: c.dir, r68: c.r68_deg, r95: c.r95_deg } : null);
      }
    } else {
      main.innerHTML = `<canvas></canvas>${s.tools ? `<div class="vis-tools"><div class="seg"><button aria-pressed="${!uncOn}" data-u="0">Normals</button><button aria-pressed="${uncOn}" data-u="1" ${B.images.unc ? '' : 'disabled'}>Uncertainty</button></div></div>` : ''}`;
      const kind = s.vis === 'normals' && uncOn ? 'unc' : s.vis;
      requestAnimationFrame(() => drawFit($('canvas', main), layer(B, kind, B.regions[sel]?.id)));
      $$('[data-u]', main).forEach((b) => b.addEventListener('click', () => { uncOn = b.dataset.u === '1'; render(); }));
    }
    side.hidden = !s.side;
    if (s.side) requestAnimationFrame(() => drawFitPlot($('canvas', side), B, sel, refOf(sel)));
    const es = $('#ex-sel', d.el);
    if (es) es.addEventListener('change', () => { sel = +es.value; render(); });
    $$('[data-zoom]', d.el).forEach((b) => b.addEventListener('click', () => zoom(b.dataset.zoom)));
  }
  const go = (i) => { step = Math.max(0, Math.min(STEPS.length - 1, i)); render(); };
  $$('.steps button', d.el).forEach((b) => b.addEventListener('click', () => go(+b.dataset.step)));
  $('#ex-prev', d.el).addEventListener('click', () => go(step - 1));
  $('#ex-next', d.el).addEventListener('click', () => (step === STEPS.length - 1 ? d.close() : go(step + 1)));
  function key(e) {
    if (document.querySelector('.zoom-figure')) return;
    const t = (e.target.tagName || '').toLowerCase();
    if (t === 'select' || t === 'input') return;
    if (e.key === 'ArrowRight') { e.preventDefault(); e.stopPropagation(); go(step + 1); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); e.stopPropagation(); go(step - 1); }
  }
  document.addEventListener('keydown', key, true);
  render();
}

function zoom(src) {
  const z = document.createElement('div');
  z.className = 'zoom-figure';
  z.setAttribute('role', 'dialog');
  z.setAttribute('aria-label', 'Enlarged figure (click or Esc to close)');
  z.tabIndex = -1;
  z.innerHTML = `<img src="${esc(src)}" alt="">`;
  const close = (e) => { if (!e || e.type === 'click' || e.key === 'Escape') { if (e) e.stopPropagation(); z.remove(); document.removeEventListener('keydown', close, true); } };
  z.addEventListener('click', close);
  document.addEventListener('keydown', close, true);
  document.body.appendChild(z);
  z.focus();
}

const AZEL_SVG = `<svg viewBox="0 0 260 150" width="100%" style="max-width:340px" role="img" aria-label="Azimuth is measured from the direction toward the camera, clockwise seen from above; elevation is the angle above the horizon.">
  <g fill="none" stroke="currentColor" stroke-width="1.2" opacity=".85">
    <circle cx="70" cy="80" r="52" opacity=".5"/><line x1="70" y1="80" x2="70" y2="132"/><line x1="70" y1="80" x2="122" y2="80"/>
    <path d="M70 120 A40 40 0 0 0 108 92" stroke="#ff8a3d"/><line x1="70" y1="80" x2="107" y2="117" stroke="#ff8a3d" stroke-width="2"/>
    <line x1="160" y1="120" x2="245" y2="120"/><line x1="170" y1="120" x2="232" y2="70" stroke="#ff8a3d" stroke-width="2"/><path d="M210 120 A40 40 0 0 0 201 96" stroke="#ff8a3d"/>
  </g>
  <g font-size="10" fill="currentColor"><text x="56" y="146">camera (az 0°)</text><text x="124" y="84">right 90°</text><text x="6" y="22">seen from above</text>
    <text x="96" y="110" fill="#ff8a3d">az</text><text x="160" y="22">seen from the side</text><text x="214" y="112" fill="#ff8a3d">el</text><text x="196" y="136">horizon 0°</text></g></svg>`;

export function openHelp() {
  const d = openDialog({ title: 'How to read this', cls: '' });
  const v = (k) => `<div class="tr">${chip(k)}<span>${esc(VERDICT_META[k].action)}</span></div>`;
  d.body.innerHTML = `<div class="help-grid">
    <section><h3 class="micro">The idea</h3>
      <p>Outdoors, one dominant light (the sun) lights every object, so surfaces facing it are brighter. LightAudit estimates, for each region, which light directions fit its shading, and checks whether one direction explains all regions. A region whose light map does not overlap the others is flagged.</p>
      <p>Drag the orange handle on the dome to try your own light: the <em>Relit</em> and <em>Residual</em> views and the "at your light" column update live. Your light never changes the audit verdict; it only drives the what-if.</p></section>
    <section><h3 class="micro">Azimuth and elevation</h3>${AZEL_SVG}
      <p>Azimuth: clockwise from the direction toward the camera, seen from above (0° = light behind the photographer, 90° = from the right). Elevation: angle above the horizon; negative = below.</p></section>
    <section><h3 class="micro">Dome legend</h3><ul>
      <li>Solid ring: 68% credible cone of a region's light. Dashed ring: 95%.</li>
      <li>White ring and yellow sun: the consensus of the reliable regions.</li>
      <li>Red pulsing ring: a flagged region. Orange handle: your light.</li>
      <li>Shell colour (dark to yellow): how well each direction explains the selected map. The lower half (below the horizon) is dimmed.</li></ul></section>
    <section><h3 class="micro">Triage</h3><div class="triage">${v('CONSISTENT')}${v('SUSPICIOUS')}${v('INSUFFICIENT')}${v('CONFLICT')}</div>
      <p style="margin-top:10px"><b>${esc(REVIEW)}</b></p></section>
    <section class="wide"><h3 class="micro">Limitations</h3><blockquote class="limits">${LIMITATIONS}</blockquote></section>
    <section class="wide"><h3 class="micro">Keyboard</h3><div class="shortcuts">
      <span><span class="kbd">1</span>–<span class="kbd">6</span></span><span>Image modes (Observed, Regions, Relit, Counterfactual, Residual, Normals)</span>
      <span><span class="kbd">←</span><span class="kbd">→</span><span class="kbd">↑</span><span class="kbd">↓</span></span><span>Move your light by 2°</span>
      <span class="kbd">R</span><span>Toggle region outlines</span><span class="kbd">H</span><span>Toggle the residual heat map</span>
      <span class="kbd">C</span><span>Toggle cones on the dome</span><span class="kbd">E</span><span>Explain stepper</span>
      <span class="kbd">A</span><span>Attack lab</span><span class="kbd">Esc</span><span>Close overlays</span>
      <span class="kbd">?</span><span>This help</span><span></span><span></span></div></section>
  </div>`;
  return d;
}

export { ICONS };
