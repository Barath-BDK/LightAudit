// Light dome (BUILD_SPEC 12.3): Three.js scene in camera space (x right, y up, z toward the viewer).
// Unit sphere shell with an EQ-grid landscape shader, the photo at the centre, per-region 68/95% cones,
// the consensus ring + sun marker, and a draggable "your light" handle.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { Line2 } from 'three/addons/lines/Line2.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { LineGeometry } from 'three/addons/lines/LineGeometry.js';
import { NA, NE, D, azElDeg, fromAzElDeg, normalize } from './grid.js';

const SHELL_VS = `
varying vec3 vDir;
void main() { vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;

const SHELL_FS = `
precision highp float;
varying vec3 vDir;
uniform sampler2D uMap;
uniform sampler2D uOverlay;
uniform int uShell;            // 0 none, 1 map, 2 all-regions overlay
uniform vec3 uBase;
uniform vec3 uGrid;
uniform float uBaseAlpha;
uniform float uFront;
const float PI = 3.14159265358979;
vec3 viridis(float t) {
  // colour constants: a neutral grey to sunlight amber (#f5b23d) to near-white ramp (6th-order fit)
  const vec3 c0 = vec3(0.146157, 0.157250, 0.186868);
  const vec3 c1 = vec3(2.017899, 1.036006, -0.717507);
  const vec3 c2 = vec3(-7.325906, -1.455478, 8.926932);
  const vec3 c3 = vec3(29.086848, 5.778844, -35.443577);
  const vec3 c4 = vec3(-49.585400, -9.851404, 60.421944);
  const vec3 c5 = vec3(35.669406, 7.086637, -43.464707);
  const vec3 c6 = vec3(-9.006650, -1.789401, 10.974990);
  return c0 + t * (c1 + t * (c2 + t * (c3 + t * (c4 + t * (c5 + t * c6)))));
}
void main() {
  vec3 d = normalize(vDir);
  float az = atan(d.x, d.z);
  float lat = asin(clamp(d.y, -1.0, 1.0));
  vec2 uv = vec2((az + PI) / (2.0 * PI), (0.5 * PI - lat) / PI);
  float azD = degrees(az), latD = degrees(lat);
  float azW = min(fwidth(azD), fwidth(mod(azD + 360.0, 360.0)));
  float gA = abs(fract(azD / 30.0 + 0.5) - 0.5) * 30.0;
  float gL = abs(fract(latD / 30.0 + 0.5) - 0.5) * 30.0;
  float lineA = (1.0 - smoothstep(0.0, azW * 1.3, gA)) * (1.0 - smoothstep(70.0, 86.0, abs(latD)));
  float lineL = 1.0 - smoothstep(0.0, fwidth(latD) * 1.3, gL);
  float eq = 1.0 - smoothstep(0.0, fwidth(latD) * 1.6, abs(latD));
  float grid = max(max(lineA, lineL) * 0.55, eq);
  vec3 col = mix(uBase, uGrid, grid);
  float a = uBaseAlpha + grid * 0.22;
  if (uShell == 1) {
    float v = clamp(texture2D(uMap, uv).r, 0.0, 1.0);
    float m = smoothstep(0.02, 0.9, v);
    col = mix(col, viridis(v), m);
    a = max(a, 0.12 + 0.78 * m);
  } else if (uShell == 2) {
    vec4 ov = texture2D(uOverlay, uv);
    col = mix(col, ov.rgb, ov.a);
    a = max(a, ov.a * 0.92);
  }
  if (d.y < 0.0) { a *= 0.42; col *= 0.75; }
  a *= uFront;
  gl_FragColor = vec4(col, a);
}`;

function css(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#000';
}

function circlePoints(c, rDeg, seg = 96, rad = 1.004) {
  c = normalize(c);
  const ref = Math.abs(c[1]) < 0.9 ? [0, 1, 0] : [1, 0, 0];
  let u = [c[1] * ref[2] - c[2] * ref[1], c[2] * ref[0] - c[0] * ref[2], c[0] * ref[1] - c[1] * ref[0]];
  u = normalize(u);
  const v = [c[1] * u[2] - c[2] * u[1], c[2] * u[0] - c[0] * u[2], c[0] * u[1] - c[1] * u[0]];
  const r = rDeg * Math.PI / 180, cr = Math.cos(r), sr = Math.sin(r);
  const pts = [];
  for (let i = 0; i <= seg; i++) {
    const t = i / seg * 2 * Math.PI, ct = Math.cos(t), st = Math.sin(t);
    for (let k = 0; k < 3; k++) pts.push(rad * (cr * c[k] + sr * (ct * u[k] + st * v[k])));
  }
  return pts;
}

function sunTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 64;
  const g = c.getContext('2d');
  g.translate(32, 32);
  g.strokeStyle = '#f5b23d'; g.lineWidth = 4; g.lineCap = 'round';
  for (let i = 0; i < 8; i++) { g.rotate(Math.PI / 4); g.beginPath(); g.moveTo(17, 0); g.lineTo(27, 0); g.stroke(); }
  g.fillStyle = '#f5b23d'; g.beginPath(); g.arc(0, 0, 12, 0, 2 * Math.PI); g.fill();
  g.strokeStyle = '#3a2a0a'; g.lineWidth = 2; g.stroke();
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

export class Dome {
  /** opts: { draggable (bool), onLight(l), labels (bool) } */
  constructor(stage, opts = {}) {
    this.stage = stage;
    this.opts = { draggable: true, labels: true, ...opts };
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: !!opts.preserve });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer = renderer;
    renderer.domElement.setAttribute('tabindex', '0');
    renderer.domElement.setAttribute('role', 'application');
    renderer.domElement.setAttribute('aria-label', 'Light dome. Drag the orange handle or use the arrow keys to move your light.');
    stage.appendChild(renderer.domElement);
    this.labelLayer = document.createElement('div');
    this.labelLayer.className = 'dome-labels';
    stage.appendChild(this.labelLayer);

    const scene = new THREE.Scene();
    this.scene = scene;
    const cam = new THREE.PerspectiveCamera(42, 1, 0.05, 50);
    cam.position.set(0.8, 0.5, 2.2).multiplyScalar(1.42);
    this.camera = cam;
    const ctl = new OrbitControls(cam, renderer.domElement);
    ctl.enableDamping = true;
    ctl.dampingFactor = 0.12;
    ctl.enablePan = false;
    ctl.minDistance = 1.6;
    ctl.maxDistance = 6;
    ctl.addEventListener('change', () => { this.dirty = true; });
    this.controls = ctl;

    // map textures
    this.mapData = new Uint16Array(D);
    this.mapTex = new THREE.DataTexture(this.mapData, NA, NE, THREE.RedFormat, THREE.HalfFloatType);
    this.ovData = new Uint8Array(D * 4);
    this.ovTex = new THREE.DataTexture(this.ovData, NA, NE, THREE.RGBAFormat, THREE.UnsignedByteType);
    for (const t of [this.mapTex, this.ovTex]) {
      t.wrapS = THREE.RepeatWrapping; t.wrapT = THREE.ClampToEdgeWrapping;
      t.magFilter = THREE.LinearFilter; t.minFilter = THREE.LinearFilter; t.generateMipmaps = false; t.needsUpdate = true;
    }
    const shellUniforms = (front) => ({
      uMap: { value: this.mapTex }, uOverlay: { value: this.ovTex }, uShell: { value: 0 },
      uBase: { value: new THREE.Color() }, uGrid: { value: new THREE.Color() }, uBaseAlpha: { value: 0.06 }, uFront: { value: front },
    });
    const geo = new THREE.SphereGeometry(1, 128, 64);
    this.shellBack = new THREE.Mesh(geo, new THREE.ShaderMaterial({ vertexShader: SHELL_VS, fragmentShader: SHELL_FS,
      uniforms: shellUniforms(0.85), side: THREE.BackSide, transparent: true, depthWrite: false }));
    this.shellFront = new THREE.Mesh(geo, new THREE.ShaderMaterial({ vertexShader: SHELL_VS, fragmentShader: SHELL_FS,
      uniforms: shellUniforms(0.55), side: THREE.FrontSide, transparent: true, depthWrite: false }));
    this.shellBack.renderOrder = 0;
    this.shellFront.renderOrder = 10;
    scene.add(this.shellBack, this.shellFront);

    // ground disc at y = 0
    this.ground = new THREE.Mesh(new THREE.CircleGeometry(1, 96), new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.07, depthWrite: false, side: THREE.DoubleSide }));
    this.ground.rotation.x = -Math.PI / 2;
    this.ground.renderOrder = 1;
    scene.add(this.ground);

    this.lineMats = [];
    this.group = new THREE.Group();      // cones, consensus (rebuilt)
    scene.add(this.group);
    this._axes();
    this._ticks();

    // photo billboard
    this.photo = new THREE.Mesh(new THREE.PlaneGeometry(0.8, 0.55), new THREE.MeshBasicMaterial({ side: THREE.DoubleSide, color: 0xffffff }));
    this.photo.renderOrder = 2;
    scene.add(this.photo);

    // sun marker for the consensus
    this.sun = new THREE.Sprite(new THREE.SpriteMaterial({ map: sunTexture(), depthTest: false, transparent: true }));
    this.sun.scale.set(0.11, 0.11, 1);
    this.sun.renderOrder = 18;
    this.sun.visible = false;
    scene.add(this.sun);

    // your light: handle + ray
    this.light = [0, 1, 0];
    this.handle = new THREE.Mesh(new THREE.SphereGeometry(0.042, 24, 16), new THREE.MeshBasicMaterial({ color: 0xf5b23d, depthTest: false }));
    this.handle.renderOrder = 20;
    this.hit = new THREE.Mesh(new THREE.SphereGeometry(0.11, 12, 8), new THREE.MeshBasicMaterial({ visible: false }));
    this.ray = this._line([0, 0, 0, 0, 1, 0], 0xf5b23d, 2, { dashed: true, dashSize: 0.04, gapSize: 0.03 });
    this.ray.renderOrder = 19;
    this.ray.material.depthTest = false;
    scene.add(this.handle, this.hit, this.ray);
    this.handle.visible = this.ray.visible = !!this.opts.draggable || !!this.opts.showLight;

    this._interaction();
    this.applyTheme();
    this.ro = new ResizeObserver(() => this.resize());
    this.ro.observe(stage);
    this.resize();
    this.reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    this._loop = this._loop.bind(this);
    this.dirty = true;
    requestAnimationFrame(this._loop);
  }

  _line(pts, color, width, extra = {}) {
    const g = new LineGeometry();
    g.setPositions(pts);
    const m = new LineMaterial({ color, linewidth: width, transparent: true, opacity: extra.opacity ?? 1, dashed: !!extra.dashed,
      dashSize: extra.dashSize ?? 0.03, gapSize: extra.gapSize ?? 0.025, worldUnits: false });
    if (this.size) m.resolution.set(this.size[0], this.size[1]);
    this.lineMats.push(m);
    const l = new Line2(g, m);
    if (extra.dashed) l.computeLineDistances();
    l.renderOrder = 5;
    return l;
  }

  _axes() {
    const ax = [[[1.25, 0, 0], 0x8e8e93], [[0, 1.25, 0], 0x8e8e93], [[0, 0, 1.25], 0x8e8e93]];
    for (const [p, c] of ax) {
      this.scene.add(this._line([0, 0, 0, ...p], c, 1, { opacity: 0.7 }));
      const head = new THREE.Mesh(new THREE.ConeGeometry(0.025, 0.07, 16), new THREE.MeshBasicMaterial({ color: c }));
      head.position.set(...p);
      head.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), new THREE.Vector3(...p).normalize());
      this.scene.add(head);
    }
    this.labels = [
      { pos: [1.36, 0, 0], text: 'right (+x)', cls: 'axis ax-x' },
      { pos: [0, 1.34, 0], text: 'up (+y)', cls: 'axis ax-y' },
      { pos: [0, 0, 1.4], text: 'toward viewer (+z)', cls: 'axis ax-z' },
      { pos: [0, -0.62, 0.72], text: 'below the horizon', cls: 'below' },
    ];
  }

  _ticks() {
    const pts = [];
    for (let a = 0; a < 360; a += 15) {
      const len = a % 45 === 0 ? 0.07 : 0.035;
      const r = a * Math.PI / 180, s = Math.sin(r), c = Math.cos(r);
      pts.push(s, 0, c, s * (1 + len), 0, c * (1 + len));
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    this.tickLines = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ transparent: true, opacity: 0.6 }));
    this.scene.add(this.tickLines);
    for (const [a, t] of [[0, '0°'], [90, '90°'], [180, '180°'], [-90, '−90°']]) {
      const r = a * Math.PI / 180;
      this.labels.push({ pos: [Math.sin(r) * 1.14, 0.03, Math.cos(r) * 1.14], text: t, cls: 'tick' });
    }
  }

  applyTheme() {
    const bg = new THREE.Color(css('--canvas-bg'));
    this.scene.background = bg;
    const light = document.documentElement.dataset.theme === 'light';
    for (const m of [this.shellBack, this.shellFront]) {
      m.material.uniforms.uBase.value.set(light ? '#8e8e93' : '#7c7c80');
      m.material.uniforms.uGrid.value.set(light ? '#48484a' : '#c7c7cc');
      m.material.uniforms.uBaseAlpha.value = light ? 0.08 : 0.05;
    }
    this.ground.material.color.set(light ? '#636366' : '#98989d');
    this.tickLines.material.color.set(light ? '#48484a' : '#a1a1a6');
    this.consColor = light ? 0x1d1d1f : 0xffffff;
    this.dirty = true;
    if (this.lastCones) this.setCones(this.lastCones, this.lastCons);
  }

  setPhoto(bitmap, W, H) {
    const t = new THREE.Texture(bitmap);
    t.colorSpace = THREE.SRGBColorSpace;
    // three.js ignores flipY for ImageBitmap sources, so flip v here (otherwise the photo is upside down)
    t.repeat.set(1, -1);
    t.offset.set(0, 1);
    t.needsUpdate = true;
    this.photo.material.map = t;
    this.photo.material.needsUpdate = true;
    this.photo.geometry.dispose();
    this.photo.geometry = new THREE.PlaneGeometry(0.8, 0.8 * H / W);
    this.dirty = true;
  }

  /** mode: 'none' | 'map' | 'overlay'. map: Float32Array(D) in [0,1]; overlay: [{ A, color '#rrggbb' }] */
  setShell(mode, map = null, overlay = null) {
    let m = 0;
    if (mode === 'map' && map) {
      for (let k = 0; k < D; k++) this.mapData[k] = THREE.DataUtils.toHalfFloat(Math.max(0, Math.min(1, map[k])));
      this.mapTex.needsUpdate = true;
      m = 1;
    } else if (mode === 'overlay' && overlay && overlay.length) {
      const cols = overlay.map((o) => new THREE.Color(o.color));
      for (let k = 0; k < D; k++) {
        let r = 0, g = 0, b = 0, wsum = 0, keep = 1;
        overlay.forEach((o, i) => {
          const a = 0.6 * Math.pow(Math.max(0, o.A[k]), 1.3);
          r += cols[i].r * a; g += cols[i].g * a; b += cols[i].b * a; wsum += a; keep *= 1 - a;
        });
        const al = 1 - keep;
        const s = wsum > 1e-6 ? 1 / wsum : 0;
        this.ovData[4 * k] = Math.round(255 * Math.min(1, r * s));
        this.ovData[4 * k + 1] = Math.round(255 * Math.min(1, g * s));
        this.ovData[4 * k + 2] = Math.round(255 * Math.min(1, b * s));
        this.ovData[4 * k + 3] = Math.round(255 * al);
      }
      this.ovTex.needsUpdate = true;
      m = 2;
    }
    this.shellBack.material.uniforms.uShell.value = m;
    this.shellFront.material.uniforms.uShell.value = m;
    this.dirty = true;
  }

  /** cones: [{ center, r68, r95, color, flagged, selected, dim, dashedOnly }]; cons: { dir, r68, r95 } or null */
  setCones(cones, cons) {
    this.lastCones = cones; this.lastCons = cons;
    for (const c of [...this.group.children]) {
      this.group.remove(c);
      c.geometry.dispose();
      const i = this.lineMats.indexOf(c.material);
      if (i >= 0) this.lineMats.splice(i, 1);
      c.material.dispose();
    }
    this.flaggedMats = [];
    for (const c of cones) {
      const op = c.dim ? 0.35 : c.selected ? 1 : 0.8;
      const w = c.selected ? 3 : 1.5;
      const col = new THREE.Color(c.color).getHex();
      if (c.r68 < 179 && !c.dashedOnly) this.group.add(this._line(circlePoints(c.center, c.r68), col, w, { opacity: op }));
      if (c.r95 < 179 && (c.selected || c.dashedOnly || c.show95)) this.group.add(this._line(circlePoints(c.center, c.r95), col, w * 0.8, { opacity: op * 0.9, dashed: true }));
      if (c.flagged) {
        const l = this._line(circlePoints(c.center, Math.min(c.r68 + 4, 178)), 0xf0524f, 2.4, { opacity: 0.9 });
        this.flaggedMats.push(l.material);
        this.group.add(l);
      }
      const dot = new THREE.Mesh(new THREE.SphereGeometry(c.selected ? 0.03 : 0.022, 16, 12), new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: op }));
      dot.position.set(...normalize(c.center));
      dot.renderOrder = 6;
      this.group.add(dot);
    }
    if (cons) {
      this.group.add(this._line(circlePoints(cons.dir, cons.r68), this.consColor ?? 0xffffff, 2.2));
      if (cons.r95 < 179) this.group.add(this._line(circlePoints(cons.dir, cons.r95), this.consColor ?? 0xffffff, 1.6, { dashed: true }));
      this.sun.position.set(...normalize(cons.dir).map((x) => x * 1.0));
      this.sun.visible = true;
    } else {
      this.sun.visible = false;
    }
    this.dirty = true;
  }

  setLight(l) {
    this.light = normalize(l);
    this.handle.position.set(...this.light);
    this.hit.position.set(...this.light);
    this.ray.geometry.setPositions([0, 0, 0, ...this.light]);
    this.ray.computeLineDistances();
    this.dirty = true;
  }

  _interaction() {
    const el = this.renderer.domElement;
    const rc = new THREE.Raycaster();
    const ndc = (e) => {
      const r = el.getBoundingClientRect();
      return new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    };
    const onSphere = (e) => {
      rc.setFromCamera(ndc(e), this.camera);
      const o = rc.ray.origin, d = rc.ray.direction;
      const b = o.dot(d), c = o.lengthSq() - 1, disc = b * b - c;
      let p;
      if (disc >= 0) p = o.clone().addScaledVector(d, -b - Math.sqrt(disc));
      else p = o.clone().addScaledVector(d, -b); // closest point of the ray to the centre -> silhouette
      return normalize([p.x, p.y, p.z]);
    };
    let dragging = false;
    el.addEventListener('pointerdown', (e) => {
      if (!this.opts.draggable) return;
      rc.setFromCamera(ndc(e), this.camera);
      if (rc.intersectObject(this.hit).length) {
        dragging = true;
        this.controls.enabled = false;
        el.setPointerCapture(e.pointerId);
        el.style.cursor = 'grabbing';
        e.preventDefault();
      }
    });
    el.addEventListener('pointermove', (e) => {
      if (dragging) {
        const l = onSphere(e);
        this.setLight(l);
        if (this.opts.onLight) this.opts.onLight(l, true);
        return;
      }
      if (!this.opts.draggable) return;
      rc.setFromCamera(ndc(e), this.camera);
      el.style.cursor = rc.intersectObject(this.hit).length ? 'grab' : '';
    });
    const end = (e) => {
      if (!dragging) return;
      dragging = false;
      this.controls.enabled = true;
      el.style.cursor = '';
      try { el.releasePointerCapture(e.pointerId); } catch { /* already released */ }
      if (this.opts.onLight) this.opts.onLight(this.light, false);
    };
    el.addEventListener('pointerup', end);
    el.addEventListener('pointercancel', end);
    el.addEventListener('dblclick', (e) => {
      if (!this.opts.draggable) return;
      const l = onSphere(e);
      this.setLight(l);
      if (this.opts.onLight) this.opts.onLight(l, false);
    });
    el.addEventListener('keydown', (e) => {
      if (!this.opts.draggable) return;
      const d = { ArrowLeft: [-2, 0], ArrowRight: [2, 0], ArrowUp: [0, 2], ArrowDown: [0, -2] }[e.key];
      if (!d) return;
      e.preventDefault();
      e.stopPropagation();
      this.nudge(d[0], d[1]);
    });
  }

  nudge(dAz, dEl) {
    let [az, el] = azElDeg(this.light);
    el = Math.max(-89.5, Math.min(89.5, el + dEl));
    az += dAz;
    const l = fromAzElDeg(az, el);
    this.setLight(l);
    if (this.opts.onLight) this.opts.onLight(l, false);
  }

  resize() {
    const w = Math.max(1, this.stage.clientWidth), h = Math.max(1, this.stage.clientHeight);
    this.renderer.setSize(w, h, true);
    this.camera.aspect = w / h;
    // fit the whole dome (radius ~1.35 with labels) into the stage at any aspect ratio
    this.camera.fov = 40;
    const half = Math.min(20, Math.atan(Math.tan(20 * Math.PI / 180) * w / h) * 180 / Math.PI) * Math.PI / 180;
    const dist = 1.38 / Math.sin(half);
    this.camera.position.normalize().multiplyScalar(Math.max(this.controls.minDistance, dist));
    this.controls.maxDistance = Math.max(6, dist * 1.5);
    this.camera.updateProjectionMatrix();
    const pr = this.renderer.getPixelRatio();
    this.size = [w * pr, h * pr];
    for (const m of this.lineMats) m.resolution.set(w * pr, h * pr);
    this.dirty = true;
  }

  _placeLabels() {
    if (!this.opts.labels) return;
    if (!this.labelEls) {
      this.labelEls = this.labels.map((l) => {
        const s = document.createElement('span');
        s.className = l.cls; s.textContent = l.text;
        this.labelLayer.appendChild(s);
        return s;
      });
    }
    const w = this.stage.clientWidth, h = this.stage.clientHeight;
    const v = new THREE.Vector3();
    this.labels.forEach((l, i) => {
      v.set(...l.pos).project(this.camera);
      const el = this.labelEls[i];
      el.style.left = `${(v.x * 0.5 + 0.5) * w}px`;
      el.style.top = `${(-v.y * 0.5 + 0.5) * h}px`;
      el.style.opacity = v.z > 1 ? 0 : 1;
    });
  }

  _loop(t) {
    if (this.destroyed) return;
    this.controls.update();
    if (this.flaggedMats && this.flaggedMats.length && !this.reduced) {
      const p = 0.55 + 0.45 * Math.sin(t / 420);
      for (const m of this.flaggedMats) m.opacity = p;
      this.dirty = true;
    }
    if (this.dirty) {
      this.renderer.render(this.scene, this.camera);
      this._placeLabels();
      this.dirty = false;
    }
    requestAnimationFrame(this._loop);
  }

  destroy() {
    this.destroyed = true;
    this.ro.disconnect();
    this.controls.dispose();
    this.renderer.dispose();
    this.renderer.forceContextLoss();
    this.stage.innerHTML = '';
  }
}
