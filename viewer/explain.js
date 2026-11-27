// Explain stepper "How this verdict was made" (BUILD_SPEC 12.6) and the Help panel (12.8).

import { openDialog, chip, ICONS, $, $$ } from './ui.js';
import { esc, VERDICT_META, REVIEW, plainWhy, regionName } from './text.js';
import { Dome } from './dome.js';

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

export function openExplain(ctx) {
  const { B, state, allRegions } = ctx;
  const f = state.fusion, regs = allRegions();
  let step = 0, dome = null;
  const reliable = f.per_region.filter((p) => p.reliable).map((p) => p.index);
  const c = f.consensus;
  const meta = VERDICT_META[f.verdict] || { word: f.verdict, action: '' };
  const agreeList = () => `<ul class="ex-list">${reliable.map((k) => {
    const p = f.per_region[k], d = state.display[k];
    return `<li><span>${esc(regionName(regs[k].name))}</span>
      <span class="v-${p.flagged ? 'SUSPICIOUS' : 'CONSISTENT'}">${p.flagged ? 'Disagrees' : 'Agrees'}</span>
      <span class="faint">${d && d.angle_deg != null ? `${d.angle_deg.toFixed(0)}° off` : ''}</span></li>`;
  }).join('')}</ul>`;

  // one idea and one picture per step
  const STEPS = [
    { title: 'One question', vis: 'photo',
      text: () => `<p>LightAudit ignores noise, compression and metadata, and looks only at the light.</p>
        <p class="ex-take">Can one light explain the shading of the whole photo?</p>` },
    { title: 'Each region votes', vis: 'regions',
      text: () => `<p>The photo is split into ${B.regions.length} regions, and each one estimates where its light comes from.</p>
        <p class="ex-take">One region, one vote for a light direction.</p>` },
    { title: 'Do the votes agree?', vis: 'dome',
      text: () => `<p>The votes are combined into one shared light${c ? `, about ${c.az_deg.toFixed(0)}° round and ${c.el_deg.toFixed(0)}° up` : ''}.</p>
        <p class="ex-take">A region far from the shared light stands out.</p>${agreeList()}` },
    { title: 'The verdict', vis: 'heat',
      text: () => `<p>Bright areas in the picture are where the shading does not fit the shared light.</p>
        <p class="ex-take"><span class="v-${f.verdict}">${esc(meta.word)}.</span> ${esc(plainWhy(f, regs))}</p>
        <p class="faint">${esc(REVIEW)}</p>` },
  ];

  const d = openDialog({ title: 'How this verdict was made', cls: 'sheet',
    foot: `<div class="dots" aria-hidden="true">${STEPS.map(() => '<i></i>').join('')}</div><span class="spacer"></span>
      <button class="btn pill quiet-pill" id="ex-prev">Back</button><button class="btn primary pill" id="ex-next">Next</button>`,
    onClose: () => { if (dome) dome.destroy(); document.removeEventListener('keydown', key, true); } });
  d.body.innerHTML = `<div class="sheet-visual" id="ex-main"></div><div class="sheet-text" id="ex-text" aria-live="polite"></div>`;

  function render() {
    const s = STEPS[step];
    $$('.dots i', d.el).forEach((x, i) => x.classList.toggle('on', i === step));
    $('#ex-prev', d.el).disabled = step === 0;
    $('#ex-next', d.el).textContent = step === STEPS.length - 1 ? 'Done' : 'Next';
    $('#ex-text', d.el).innerHTML = `<h3>${esc(s.title)}</h3>${s.text()}`;
    const main = $('#ex-main', d.el);
    if (s.vis !== 'dome' && dome) { dome.destroy(); dome = null; }
    if (s.vis === 'dome') {
      if (!dome) {
        main.innerHTML = '';
        dome = new Dome(main, { draggable: false, labels: false });
        dome.setPhoto(B.images.image.bitmap, B.W, B.H);
        dome.applyTheme();
      }
      dome.setShell(f.consensus_map ? 'map' : 'none', f.consensus_map);
      dome.setCones(reliable.filter((k) => f.per_region[k].flagged).map((k) => ({ center: regs[k].center, r68: regs[k].r68_deg, r95: regs[k].r95_deg, color: regs[k].color, flagged: true })),
        c ? { dir: c.dir, r68: c.r68_deg, r95: c.r95_deg } : null);
    } else {
      main.innerHTML = '<canvas></canvas>';
      requestAnimationFrame(() => drawFit($('canvas', main), layer(B, s.vis)));
    }
  }
  const go = (i) => { step = Math.max(0, Math.min(STEPS.length - 1, i)); render(); };
  $('#ex-prev', d.el).addEventListener('click', () => go(step - 1));
  $('#ex-next', d.el).addEventListener('click', () => (step === STEPS.length - 1 ? d.close() : go(step + 1)));
  function key(e) {
    const t = (e.target.tagName || '').toLowerCase();
    if (t === 'select' || t === 'input') return;
    if (e.key === 'ArrowRight') { e.preventDefault(); e.stopPropagation(); go(step + 1); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); e.stopPropagation(); go(step - 1); }
  }
  document.addEventListener('keydown', key, true);
  render();
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
