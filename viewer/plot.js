// Landing hero: the real pear photo on black with a sun you drag round it. Every move recomputes each region's agreement
// with your light through fusion.whatIf() on the bundle's own light maps (landscapes.bin). Agreement is shown as light,
// never as a colour wash: a region that rejects your light falls into shade, one that accepts it gets a warm rim.
// The flagged patch keeps its outline: the audit flagged it with the panel test, which does not depend on your light.

import { D, azElDeg } from './grid.js';
import { whatIf, DEFAULT_CFG } from './fusion.js';

const NS = 'http://www.w3.org/2000/svg';
const svgEl = (name, attrs = {}) => {
  const n = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
};
const loadImg = (src) => new Promise((ok, bad) => { const im = new Image(); im.onload = () => ok(im); im.onerror = bad; im.src = src; });
const SUN = [245, 178, 61];

/** Light direction from the ring angle phi (0 = up, clockwise) and the tilt theta away from the camera axis (degrees). */
function lightOf(phi, theta) {
  const p = phi * Math.PI / 180, t = theta * Math.PI / 180;
  return [Math.sin(t) * Math.sin(p), Math.sin(t) * Math.cos(p), Math.cos(t)];
}

export async function initHero(stage, live, base) {
  if (!stage) return;
  let m, maps, img, lab;
  try {
    m = await (await fetch(base + 'manifest.json')).json();
    const all = new Float32Array(await (await fetch(base + 'landscapes.bin')).arrayBuffer());
    maps = m.regions.map((r) => all.subarray(r.landscape_index * D, (r.landscape_index + 1) * D));
    [img, lab] = await Promise.all([loadImg(base + 'image.png'), loadImg(base + 'labels.png')]);
  } catch {
    live.textContent = 'The hero photo could not be loaded. Open any audited photo below.';
    return;
  }
  const W = img.width, H = img.height;
  const regions = m.regions;
  const flaggedIds = new Set((m.fusion.per_region || []).filter((p) => p.flagged).map((p) => p.id));
  const cfg = { ...DEFAULT_CFG, ...(m.calibration || {}) };
  const weights = regions.map((r) => r.weight), excluded = regions.map((r) => !!r.excluded);

  // per-region shade masks (black fill), rims (sun-coloured edge) and the flagged outline, built once from labels.png
  const c0 = document.createElement('canvas'); c0.width = W; c0.height = H;
  const x0 = c0.getContext('2d', { willReadFrequently: true });
  x0.drawImage(lab, 0, 0);
  const L = x0.getImageData(0, 0, W, H).data;
  const layer = (test, rgb) => {
    const c = document.createElement('canvas'); c.width = W; c.height = H;
    const g = c.getContext('2d'), d = g.createImageData(W, H);
    for (let y = 1; y < H - 1; y++) for (let x = 1; x < W - 1; x++) {
      const k = y * W + x;
      if (!test(k, x, y)) continue;
      d.data[4 * k] = rgb[0]; d.data[4 * k + 1] = rgb[1]; d.data[4 * k + 2] = rgb[2]; d.data[4 * k + 3] = 255;
    }
    g.putImageData(d, 0, 0);
    return c;
  };
  const masks = regions.map((r) => layer((k) => L[4 * k] === r.id, [0, 0, 0]));
  const rims = regions.map((r) => layer((k) => L[4 * k] === r.id
    && (L[4 * (k - 1)] !== r.id || L[4 * (k + 1)] !== r.id || L[4 * (k - W)] !== r.id || L[4 * (k + W)] !== r.id), SUN));
  const outline = document.createElement('canvas'); outline.width = W; outline.height = H;
  {
    const g = outline.getContext('2d'), d = g.createImageData(W, H);
    const bad = getComputedStyle(document.documentElement).getPropertyValue('--bad').trim() || '#ef5a5a';
    const [cr, cg, cb] = [1, 3, 5].map((i) => parseInt(bad.slice(i, i + 2), 16));
    const id = (x, y) => L[4 * (y * W + x)];
    for (let y = 2; y < H - 2; y++) for (let x = 2; x < W - 2; x++) {
      const v = id(x, y);
      if (!flaggedIds.has(v)) continue;
      if ([1, 2].some((s) => id(x - s, y) !== v || id(x + s, y) !== v || id(x, y - s) !== v || id(x, y + s) !== v)) {
        const k = 4 * (y * W + x); d.data[k] = cr; d.data[k + 1] = cg; d.data[k + 2] = cb; d.data[k + 3] = 255;
      }
    }
    g.putImageData(d, 0, 0);
  }

  const canvas = stage.querySelector('#hv-canvas'), svg = stage.querySelector('#hero-svg');
  const ctx = canvas.getContext('2d');
  let phi = 0, theta = 26, geo = null, agree = regions.map(() => 0);

  // ring, beams and sun handle
  const ring = svgEl('circle', { class: 'h-ring' });
  const beams = regions.map((r) => svgEl('line', { class: `h-beam${flaggedIds.has(r.id) ? ' flag' : ''}` }));
  const sun = svgEl('g', { class: 'h-sun', tabindex: '0', role: 'slider', 'aria-label': 'Sun. Drag round the photo, or use the arrow keys',
    'aria-valuemin': '0', 'aria-valuemax': '360' });
  sun.append(svgEl('circle', { r: 26, class: 'h-sun-glow' }), svgEl('circle', { r: 9, class: 'h-sun-core' }));
  svg.append(ring, ...beams, sun);

  function layout() {
    const s = stage.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(s.width * dpr); canvas.height = Math.round(s.height * dpr);
    svg.setAttribute('viewBox', `0 0 ${s.width} ${s.height}`);
    const R = Math.min(s.width, s.height) / 2 - 22;
    const ph = R * 1.8, pw = ph * W / H;       // the photo's black corners may cross the ring; the pear stays inside
    geo = { w: s.width, h: s.height, cx: s.width / 2, cy: s.height / 2, R, pw, ph, dpr };
    ring.setAttribute('cx', geo.cx); ring.setAttribute('cy', geo.cy); ring.setAttribute('r', R);
    draw();
  }

  function draw() {
    if (!geo) return;
    const { cx, cy, R, pw, ph, dpr } = geo;
    const l = lightOf(phi, theta);
    let res = null;
    try { res = whatIf(maps, weights, excluded, l, cfg); } catch { /* keep the last glow */ }
    if (res) agree = res.per_region.map((p) => (p.reliable ? p.agreement : 0));
    const px = cx - pw / 2, py = cy - ph / 2;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, geo.w, geo.h);
    ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
    ctx.drawImage(img, px, py, pw, ph);
    regions.forEach((r, i) => { ctx.globalAlpha = (1 - Math.min(1, agree[i])) * 0.62; ctx.drawImage(masks[i], px, py, pw, ph); });
    ctx.shadowColor = 'rgba(245, 178, 61, .9)'; ctx.shadowBlur = 14;
    regions.forEach((r, i) => {
      if (flaggedIds.has(r.id)) return;
      ctx.globalAlpha = Math.min(1, agree[i]) * 0.9; ctx.drawImage(rims[i], px, py, pw, ph);
    });
    ctx.shadowBlur = 0; ctx.globalAlpha = 1;
    ctx.drawImage(outline, px, py, pw, ph);
    const t = phi * Math.PI / 180, sx = cx + R * Math.sin(t), sy = cy - R * Math.cos(t);
    sun.setAttribute('transform', `translate(${sx.toFixed(1)} ${sy.toFixed(1)})`);
    regions.forEach((r, i) => {
      const [b0, b1, b2, b3] = r.bbox;
      const cx2 = px + (b0 + b2) / 2 / W * pw, cy2 = py + (b1 + b3) / 2 / H * ph;
      const tx = sx + (cx2 - sx) * 0.42, ty = sy + (cy2 - sy) * 0.42;   // beams point at their region and stop short of the photo
      Object.entries({ x1: sx, y1: sy, x2: tx, y2: ty }).forEach(([k, v]) => beams[i].setAttribute(k, v.toFixed(1)));
      beams[i].style.opacity = (0.08 + 0.72 * Math.min(1, agree[i])).toFixed(2);
    });
    stage.style.setProperty('--gx', `${(sx + 0.8 * geo.w).toFixed(0)}px`);   // ::before is inset -80%
    stage.style.setProperty('--gy', `${(sy + 0.8 * geo.h).toFixed(0)}px`);
    const [az, el] = azElDeg(l);
    sun.setAttribute('aria-valuenow', String(Math.round(((phi % 360) + 360) % 360)));
    sun.setAttribute('aria-valuetext', `light from azimuth ${Math.round(az)} degrees, elevation ${Math.round(el)} degrees`);
    live.textContent = sentence();
  }

  // One sentence from the live agreements: the genuine regions against the flagged patch.
  function sentence() {
    const gi = regions.map((r, i) => i).filter((i) => !flaggedIds.has(regions[i].id) && !excluded[i]);
    const fi = regions.map((r, i) => i).filter((i) => flaggedIds.has(regions[i].id));
    if (!gi.length || !fi.length) return '';
    const g = gi.reduce((s, i) => s + agree[i], 0) / gi.length, f = Math.max(...fi.map((i) => agree[i]));
    if (g >= 0.5 && f < 0.25) return 'This light fits the real pear. The pasted patch stays dark.';
    if (f >= 0.5 && g < 0.25) return 'This light fits the pasted patch. The rest of the pear goes dark.';
    if (g >= 0.5 && f >= 0.5) return 'Both sides accept this light. The patch is still flagged: its brightness does not match the surface around it.';
    return 'Neither side fits this light well. Keep turning the sun.';
  }

  const fromPointer = (e) => {
    const r = svg.getBoundingClientRect();
    phi = Math.atan2(e.clientX - r.left - geo.cx, -(e.clientY - r.top - geo.cy)) * 180 / Math.PI;
    draw();
  };
  let drag = false;
  sun.addEventListener('pointerdown', (e) => { stopIntro(); drag = true; sun.setPointerCapture(e.pointerId); e.preventDefault(); });
  sun.addEventListener('pointermove', (e) => { if (drag) fromPointer(e); });
  sun.addEventListener('pointerup', () => { drag = false; });
  ring.addEventListener('pointerdown', (e) => { stopIntro(); fromPointer(e); });
  sun.addEventListener('keydown', (e) => {
    const d = { ArrowLeft: [-4, 0], ArrowRight: [4, 0], ArrowUp: [0, -4], ArrowDown: [0, 4] }[e.key];
    if (!d) return;
    e.preventDefault(); stopIntro();
    phi += d[0]; theta = Math.max(6, Math.min(80, theta + d[1]));
    draw();
  });

  // one authored moment: the sun swings in from the patch's side to the pear's light, unless motion is reduced
  let raf = 0;
  const stopIntro = () => { if (raf) cancelAnimationFrame(raf); raf = 0; };
  new ResizeObserver(layout).observe(stage);
  layout();
  if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const t0 = performance.now(), T = 2200, from = 80;
    const step = (t) => {
      const k = Math.min(1, (t - t0) / T), e = 1 - (1 - k) ** 4;
      phi = from * (1 - e);
      draw();
      raf = k < 1 ? requestAnimationFrame(step) : 0;
    };
    raf = requestAnimationFrame(step);
  }
  stage.classList.add('ready');
}
