// Cue C4 (experimental): manual cast-shadow pairs. Mirror of lightaudit/cues/shadow_pairs.py.
// The user clicks an object point p, then the point s where its shadow falls. For a directional light, the plane
// through the camera centre and the rays r(p), r(s) contains the light direction: l . m = 0 with m = r(p) x r(s).
// Sign: the shadow lies further along -l, so the image motion p -> s must follow the projection of -l.

import { D, DIRS, pixelRay, hpd, coneHalfAngleDeg } from './grid.js';
import { mapArgmax } from './fusion.js';
import { esc } from './text.js';

/** pairs = [[[pu, pv], [su, sv]], ...] in pixels; needs >= 2 pairs. Returns Float32Array(D) in [0,1] or null. */
export function shadowLandscape(pairs, H, W, fovDeg = 60, sigmaPx = 3) {
  if (pairs.length < 2) return null;
  const r2 = new Float64Array(D), ok = new Uint8Array(D).fill(1);
  for (const [[pu, pv], [su, sv]] of pairs) {
    const rp = pixelRay(pu, pv, W, H, fovDeg), rs = pixelRay(su, sv, W, H, fovDeg);
    let m = [rp[1] * rs[2] - rp[2] * rs[1], rp[2] * rs[0] - rp[0] * rs[2], rp[0] * rs[1] - rp[1] * rs[0]];
    const mn = Math.max(Math.hypot(...m), 1e-9);
    m = m.map((x) => x / mn);
    const sig = sigmaPx / Math.max(Math.hypot(su - pu, sv - pv), 1);
    const dd = [rs[0] - rp[0], rs[1] - rp[1], rs[2] - rp[2]];
    for (let k = 0; k < D; k++) {
      const x = DIRS[3 * k], y = DIRS[3 * k + 1], z = DIRS[3 * k + 2];
      const lm = Math.abs(x * m[0] + y * m[1] + z * m[2]);
      r2[k] += (Math.asin(Math.min(1, lm)) / sig) ** 2;
      const lp = x * rp[0] + y * rp[1] + z * rp[2];
      const t = -((x - lp * rp[0]) * dd[0] + (y - lp * rp[1]) * dd[1] + (z - lp * rp[2]) * dd[2]);
      if (!(t > 0)) ok[k] = 0;
    }
  }
  const A = new Float32Array(D);
  let mx = 0;
  for (let k = 0; k < D; k++) { A[k] = ok[k] ? Math.exp(-r2[k] / 2) : 0; if (A[k] > mx) mx = A[k]; }
  if (mx <= 0) return null;
  for (let k = 0; k < D; k++) A[k] /= mx;
  return A;
}

export class ShadowTool {
  constructor({ stage, canvas, view, bundle, cfg, button, onChange }) {
    Object.assign(this, { stage, canvas, view, bundle, cfg, button, onChange });
    this.pairs = [];
    this.pending = null;
    this.active = false;
  }

  toggle(force) {
    this.active = force === undefined ? !this.active : force;
    this.button.setAttribute('aria-pressed', String(this.active));
    this.stage.classList.toggle('picking', this.active);
    if (this.active) this._panel(); else if (this.panel) { this.panel.remove(); this.panel = null; }
    this.draw();
  }

  _panel() {
    if (this.panel) this.panel.remove();
    const p = document.createElement('div');
    p.className = 'shadow-panel';
    p.setAttribute('role', 'region');
    p.setAttribute('aria-label', 'Shadow-pair tool');
    this.stage.appendChild(p);
    this.panel = p;
    this._renderPanel();
  }

  _renderPanel() {
    if (!this.panel) return;
    const n = this.pairs.length;
    this.panel.innerHTML = `<div class="row"><b>Shadow pairs</b><span class="exp-badge">experimental</span></div>
      <p>${this.pending ? 'Now click where the shadow of that point falls.' : 'Click a point on an object (e.g. the top of a pole), then the matching point of its cast shadow.'}
      Two or more pairs add a scene-level cue to the fusion (weight ${this.cfg().w_shadow ?? 0.7}).</p>
      <div class="row"><span class="mono">${n} pair${n === 1 ? '' : 's'}${n >= 2 && !this.inconsistent ? ' · in fusion' : ''}</span></div>
      ${this.inconsistent ? '<p style="color:var(--conflict)">No single distant light fits these pairs (the shadows point in incompatible directions). Not added to the fusion.</p>' : ''}
      <div class="row"><button class="btn sm" data-a="undo" ${n || this.pending ? '' : 'disabled'}>Undo</button>
        <button class="btn sm" data-a="clear" ${n || this.pending ? '' : 'disabled'}>Clear</button>
        <button class="btn sm" data-a="done">Done</button></div>`;
    this.panel.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => {
      const a = b.dataset.a;
      if (a === 'undo') { if (this.pending) this.pending = null; else this.pairs.pop(); this._update(); }
      if (a === 'clear') { this.pairs = []; this.pending = null; this._update(); }
      if (a === 'done') this.toggle(false);
    }));
  }

  click(p) {
    if (!this.pending) this.pending = p;
    else { this.pairs.push([this.pending, p]); this.pending = null; }
    this._update();
  }

  _update() {
    const b = this.bundle;
    const A = shadowLandscape(this.pairs, b.H, b.W, b.manifest.image.fov_deg || 60, 3);
    this.inconsistent = !A && this.pairs.length >= 2;
    this._renderPanel();
    this.draw();
    if (!A) { this.onChange(null); return; }
    const { fracs: [f68, f95] } = hpd(A);
    const ids = b.regions.map((r) => r.id);
    this.onChange({
      id: Math.max(0, ...ids) + 1, name: 'shadow pairs', kind: 'pseudo', excluded: false, A, weight: this.cfg().w_shadow ?? 0.7,
      cues: ['shadow'], center: mapArgmax(A).dir, r68_deg: coneHalfAngleDeg(f68), r95_deg: coneHalfAngleDeg(f95),
      color: '#ff8a3d', n_valid: this.pairs.length, reason: null, factors: null, area_px: 0,
    });
  }

  draw() {
    const c = this.canvas, dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.round(c.clientWidth * dpr), h = Math.round(c.clientHeight * dpr);
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    const g = c.getContext('2d');
    g.clearRect(0, 0, w, h);
    if (!this.pairs.length && !this.pending) return;
    const r = this.view.cssRect(), b = this.bundle;
    const P = ([u, v]) => [(r.x + u / b.W * r.w) * dpr, (r.y + v / b.H * r.h) * dpr];
    g.lineWidth = 2 * dpr;
    for (const [p, s] of this.pairs) {
      const [x1, y1] = P(p), [x2, y2] = P(s);
      // extend the line to show where pairs converge (the light's vanishing point)
      const dx = x2 - x1, dy = y2 - y1;
      g.strokeStyle = 'rgba(255,138,61,.45)'; g.setLineDash([5 * dpr, 4 * dpr]);
      g.beginPath(); g.moveTo(x1 - dx * 6, y1 - dy * 6); g.lineTo(x2 + dx * 6, y2 + dy * 6); g.stroke();
      g.setLineDash([]); g.strokeStyle = '#ff8a3d';
      g.beginPath(); g.moveTo(x1, y1); g.lineTo(x2, y2); g.stroke();
      g.fillStyle = '#ff8a3d'; g.beginPath(); g.arc(x1, y1, 4 * dpr, 0, 7); g.fill();
      g.fillStyle = '#111'; g.strokeStyle = '#ff8a3d'; g.beginPath(); g.arc(x2, y2, 4 * dpr, 0, 7); g.fill(); g.stroke();
    }
    if (this.pending) {
      const [x, y] = P(this.pending);
      g.fillStyle = '#ff8a3d'; g.beginPath(); g.arc(x, y, 5 * dpr, 0, 7); g.fill();
    }
  }
}

export { esc };
