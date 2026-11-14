// Image view: WebGL2 relighting renderer (BUILD_SPEC 12.2).
// Modes: observed | regions | relit | counterfactual | residual | normals.
// Region parameters live in an RGBA32F data texture (12 x 64 texels, row = label id):
//   texels 0..8  g_lut (33 knots)     texel 9  sigma, slope, weight, hasResidual
//   texel 10     reference light xyz (the light the LUT was fitted against), 1
//   texel 11     colour rgb, status (0 none, 1 ok, 2 excluded, 3 flagged, 4 unreliable)

export const MODES = ['observed', 'regions', 'relit', 'counterfactual', 'residual', 'normals'];
export const MODE_LABELS = { observed: 'Observed', regions: 'Regions', relit: 'Relit', counterfactual: 'Counterfactual', residual: 'Residual', normals: 'Normals' };

const VS = `#version 300 es
in vec2 aPos;
out vec2 vUv;
void main() { vUv = vec2(aPos.x * 0.5 + 0.5, 0.5 - aPos.y * 0.5); gl_Position = vec4(aPos, 0.0, 1.0); }`;

const FS = `#version 300 es
precision highp float; precision highp int; precision highp sampler2D;
in vec2 vUv; out vec4 o;
uniform sampler2D uImage, uNormals, uUnc, uHeat, uCf, uLabels, uParams;
uniform vec2 uSize;       // image size in pixels
uniform int uMode;        // 0..5 display modes, 6 = raw residual at the per-region reference light (heat check)
uniform vec3 uLight;
uniform int uSpec;        // 0 off, 1 Blinn-Phong, 2 GGX
uniform float uSpecK, uShin, uRough, uFov, uHeatGain, uSplit, uPulse;
uniform int uOutline, uSelected, uHover;

const vec3 LUMA = vec3(0.2126, 0.7152, 0.0722);

vec4 P(int id, int t) { return texelFetch(uParams, ivec2(t, id), 0); }
float lutAt(int id, int i) { vec4 t = P(id, i / 4); int c = i - (i / 4) * 4; return c == 0 ? t.x : c == 1 ? t.y : c == 2 ? t.z : t.w; }
float g(int id, float s) {
  float x = clamp(s, 0.0, 1.0) * 32.0; int i = min(int(floor(x)), 31); float f = x - float(i);
  return mix(lutAt(id, i), lutAt(id, i + 1), f);
}
int labelAt(ivec2 p) { p = clamp(p, ivec2(0), ivec2(uSize) - 1); return int(texelFetch(uLabels, p, 0).r * 255.0 + 0.5); }

vec3 inferno(float t) {
  t = clamp(t, 0.0, 1.0);
  const vec3 c0 = vec3(0.0002189403691192265, 0.001651004631001012, -0.01948089843709184);
  const vec3 c1 = vec3(0.1065134194856116, 0.5639564367884091, 3.932712388889277);
  const vec3 c2 = vec3(11.60249308247187, -3.972853965665698, -15.9423941062914);
  const vec3 c3 = vec3(-41.70399613139459, 17.43639888205313, 44.35414519872813);
  const vec3 c4 = vec3(77.162935699427, -33.40235894210092, -81.80730925738993);
  const vec3 c5 = vec3(-71.31942824499214, 32.62606426397723, 73.20951985803202);
  const vec3 c6 = vec3(25.13112622477341, -12.24266895238567, -23.07032500287172);
  return clamp(c0 + t * (c1 + t * (c2 + t * (c3 + t * (c4 + t * (c5 + t * c6))))), 0.0, 1.0);
}

float zAt(int id, vec3 n, float Y, float uncDeg, vec3 l) {
  vec4 q = P(id, 9);
  float yh = g(id, max(0.0, dot(n, l)));
  float u = radians(uncDeg);
  return abs(Y - yh) / sqrt(q.x * q.x + (q.y * u) * (q.y * u));
}

void main() {
  ivec2 px = ivec2(floor(vUv * uSize));
  vec3 rgb = texture(uImage, vUv).rgb;
  int id = labelAt(px);
  vec4 meta = P(id, 11);
  int status = int(meta.w + 0.5);
  vec4 q = P(id, 9);
  bool hasRes = id > 0 && q.w > 0.5;
  vec3 n = normalize(texture(uNormals, vUv).rgb * 2.0 - 1.0);
  float Y = dot(rgb, LUMA);
  float unc = texture(uUnc, vUv).r * 45.0;

  if (uMode == 6) {   // exact check against heat.png: residual at each region's own reference light
    float z = hasRes ? zAt(id, n, Y, unc, P(id, 10).xyz) : 0.0;
    o = vec4(vec3(clamp(z / 4.0, 0.0, 1.0)), 1.0);
    return;
  }
  int mode = (uSplit > 0.0 && vUv.x < uSplit) ? 0 : uMode;
  vec3 col = rgb;
  if (mode == 1) {
    if (id > 0) {
      col = mix(rgb, meta.rgb, 0.45);
      if (status == 2) {   // excluded: hatched
        float h = mod(gl_FragCoord.x + gl_FragCoord.y, 9.0);
        col = h < 2.5 ? mix(col, vec3(0.5), 0.7) : mix(rgb, vec3(dot(rgb, LUMA)), 0.6) * 0.7;
      }
    }
  } else if (mode == 2) {
    if (hasRes && status != 2) {
      float yRef = g(id, max(0.0, dot(n, P(id, 10).xyz)));
      float yNew = g(id, max(0.0, dot(n, uLight)));
      col = rgb * (yNew + 0.01) / (yRef + 0.01);
      if (uSpec > 0) {
        float f = (uSize.x * 0.5) / tan(radians(uFov) * 0.5);
        vec2 uv = vec2(px) + 0.5;
        vec3 v = normalize(vec3(-(uv.x - uSize.x * 0.5) / f, (uv.y - uSize.y * 0.5) / f, 1.0));
        float nl = dot(n, uLight), nv = max(dot(n, v), 1e-3);
        if (nl > 0.0) {
          vec3 h = normalize(uLight + v);
          float nh = max(dot(n, h), 0.0), s;
          if (uSpec == 1) s = uSpecK * pow(nh, uShin);
          else {
            float a = uRough * uRough, a2 = a * a;
            float dd = nh * nh * (a2 - 1.0) + 1.0;
            float Dg = a2 / (3.14159265 * dd * dd);
            float k = (uRough + 1.0) * (uRough + 1.0) / 8.0;
            float G = (nl / (nl * (1.0 - k) + k)) * (nv / (nv * (1.0 - k) + k));
            float F = 0.04 + 0.96 * pow(1.0 - max(dot(v, h), 0.0), 5.0);
            s = uSpecK * 4.0 * Dg * G * F / (4.0 * nl * nv) * nl;
          }
          col += vec3(s);
        }
      }
      col = clamp(col, 0.0, 1.0);
    }
  } else if (mode == 3) {
    col = texture(uCf, vUv).rgb;
  } else if (mode == 4) {
    vec3 grey = vec3(Y) * 0.32;
    col = hasRes ? inferno(zAt(id, n, Y, unc, uLight) / 4.0 * uHeatGain) : grey;
  } else if (mode == 5) {
    col = id >= 0 ? n * 0.5 + 0.5 : rgb;
  }

  if (uOutline > 0 && id > 0) {
    bool edge = labelAt(px + ivec2(1, 0)) != id || labelAt(px - ivec2(1, 0)) != id ||
                labelAt(px + ivec2(0, 1)) != id || labelAt(px - ivec2(0, 1)) != id;
    if (edge) {
      if (id == uSelected) col = vec3(1.0, 0.54, 0.24);
      else if (id == uHover) col = vec3(1.0);
      else if (status == 3) col = mix(vec3(0.94, 0.32, 0.31), vec3(1.0, 0.7, 0.7), uPulse);
      else if (mode == 1) col = meta.rgb;
    }
  }
  o = vec4(col, 1.0);
}`;

function compile(gl, type, src) {
  const s = gl.createShader(type);
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
  return s;
}

export class ImageView {
  constructor(canvas) {
    this.canvas = canvas;
    const gl = canvas.getContext('webgl2', { antialias: false, preserveDrawingBuffer: false });
    if (!gl) throw new Error('WebGL2 is not available in this browser.');
    this.gl = gl;
    const p = gl.createProgram();
    gl.attachShader(p, compile(gl, gl.VERTEX_SHADER, VS));
    gl.attachShader(p, compile(gl, gl.FRAGMENT_SHADER, FS));
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    this.prog = p;
    this.u = {};
    for (const n of ['uImage', 'uNormals', 'uUnc', 'uHeat', 'uCf', 'uLabels', 'uParams', 'uSize', 'uMode', 'uLight', 'uSpec',
      'uSpecK', 'uShin', 'uRough', 'uFov', 'uHeatGain', 'uSplit', 'uPulse', 'uOutline', 'uSelected', 'uHover']) {
      this.u[n] = gl.getUniformLocation(p, n);
    }
    const vb = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, vb);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    this.vao = gl.createVertexArray();
    gl.bindVertexArray(this.vao);
    const loc = gl.getAttribLocation(p, 'aPos');
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    this.tex = {};
    this.params = new Float32Array(12 * 64 * 4);
    this.opts = { mode: 'observed', light: [0, 1, 0], spec: 0, specK: 0.6, shin: 80, rough: 0.35, heatGain: 1, split: 0,
      outline: 1, selected: -1, hover: -1, pulse: 0 };
    this.rect = { x: 0, y: 0, w: 1, h: 1 };
    this.dirty = true;
    this._loop = this._loop.bind(this);
    this.ro = new ResizeObserver(() => { this.resize(); });
    this.ro.observe(canvas.parentElement);
    requestAnimationFrame(this._loop);
  }

  _texture(name, src, nearest = false) {
    const gl = this.gl;
    const t = this.tex[name] || gl.createTexture();
    this.tex[name] = t;
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
    if (src && src.bitmap) gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, src.bitmap);
    else gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([128, 128, 255, 255]));
    const f = nearest ? gl.NEAREST : gl.LINEAR;
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, f);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, f);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  }

  setBundle(b) {
    this.b = b;
    const im = b.images;
    this._texture('uImage', im.image);
    this._texture('uNormals', im.normals);
    this._texture('uUnc', im.unc);
    this._texture('uHeat', im.heat);
    this._texture('uCf', im.counterfactual || im.image);
    this._texture('uLabels', im.labels, true);
    this.resize();
  }

  /** rows: [{ id, lut[33], sigma, slope, weight, hasRes, ref[3], color[3], status }] */
  setRegions(rows) {
    const P = this.params;
    P.fill(0);
    for (const r of rows) {
      if (r.id < 0 || r.id > 63) continue;
      const o = r.id * 12 * 4;
      for (let i = 0; i < 33; i++) P[o + i] = r.lut ? r.lut[i] : i / 32;
      P.set([r.sigma, r.slope, r.weight, r.hasRes ? 1 : 0], o + 36);
      P.set([r.ref[0], r.ref[1], r.ref[2], 1], o + 40);
      P.set([r.color[0], r.color[1], r.color[2], r.status], o + 44);
    }
    const gl = this.gl;
    if (!this.tex.uParams) this.tex.uParams = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, this.tex.uParams);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA32F, 12, 64, 0, gl.RGBA, gl.FLOAT, P);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    this.rows = rows;
    this.dirty = true;
  }

  set(opts) { Object.assign(this.opts, opts); this.dirty = true; }

  resize() {
    const c = this.canvas, el = c.parentElement;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(1, Math.round(el.clientWidth * dpr)), h = Math.max(1, Math.round(el.clientHeight * dpr));
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    if (this.b) {
      const pad = 10 * dpr;
      const s = Math.min((w - 2 * pad) / this.b.W, (h - 2 * pad) / this.b.H);
      const rw = Math.max(1, Math.floor(this.b.W * s)), rh = Math.max(1, Math.floor(this.b.H * s));
      this.rect = { x: Math.floor((w - rw) / 2), y: Math.floor((h - rh) / 2), w: rw, h: rh, dpr };
    }
    this.dirty = true;
    if (this.onResize) this.onResize(this.cssRect());
  }

  /** Image rectangle in CSS pixels relative to the canvas. */
  cssRect() {
    const r = this.rect, d = r.dpr || 1;
    return { x: r.x / d, y: (this.canvas.height - r.y - r.h) / d, w: r.w / d, h: r.h / d };
  }

  /** CSS client coordinates -> image pixel coordinates (float), or null outside the image. */
  toImage(clientX, clientY) {
    const b = this.canvas.getBoundingClientRect(), r = this.cssRect();
    const u = (clientX - b.left - r.x) / r.w * this.b.W, v = (clientY - b.top - r.y) / r.h * this.b.H;
    return (u < 0 || v < 0 || u >= this.b.W || v >= this.b.H) ? null : [u, v];
  }

  _bind(mode) {
    const gl = this.gl, u = this.u, o = this.opts;
    gl.useProgram(this.prog);
    gl.bindVertexArray(this.vao);
    const names = ['uImage', 'uNormals', 'uUnc', 'uHeat', 'uCf', 'uLabels', 'uParams'];
    names.forEach((n, i) => { gl.activeTexture(gl.TEXTURE0 + i); gl.bindTexture(gl.TEXTURE_2D, this.tex[n]); gl.uniform1i(u[n], i); });
    gl.uniform2f(u.uSize, this.b.W, this.b.H);
    gl.uniform1i(u.uMode, mode);
    gl.uniform3fv(u.uLight, o.light);
    gl.uniform1i(u.uSpec, o.spec);
    gl.uniform1f(u.uSpecK, o.specK);
    gl.uniform1f(u.uShin, o.shin);
    gl.uniform1f(u.uRough, o.rough);
    gl.uniform1f(u.uFov, this.b.manifest.image.fov_deg || 60);
    gl.uniform1f(u.uHeatGain, o.heatGain);
    gl.uniform1f(u.uSplit, mode === 6 ? 0 : o.split);
    gl.uniform1f(u.uPulse, o.pulse);
    gl.uniform1i(u.uOutline, mode === 6 ? 0 : o.outline);
    gl.uniform1i(u.uSelected, o.selected);
    gl.uniform1i(u.uHover, o.hover);
  }

  render() {
    if (!this.b || !this.tex.uParams) return;
    const gl = this.gl, r = this.rect;
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.viewport(r.x, r.y, r.w, r.h);
    this._bind(MODES.indexOf(this.opts.mode));
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    this.dirty = false;
  }

  _loop(t) {
    if (this.destroyed) return;
    if (this.animatePulse) { this.opts.pulse = 0.5 + 0.5 * Math.sin(t / 380); this.dirty = true; }
    if (this.dirty) this.render();
    requestAnimationFrame(this._loop);
  }

  /** Renders the residual at each region's reference light (the export's l_ref) at native resolution and compares
   *  it with heat.png. Returns { n, within2, within8, meanAbs, maxAbs } over pixels where either map is non-zero. */
  heatCheck() {
    const b = this.b, gl = this.gl;
    if (!b.images.heat || !this.tex.uParams) return null;
    const fb = gl.createFramebuffer(), t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, b.W, b.H, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t, 0);
    gl.viewport(0, 0, b.W, b.H);
    this._bind(6);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    const out = new Uint8Array(b.W * b.H * 4);
    gl.readPixels(0, 0, b.W, b.H, gl.RGBA, gl.UNSIGNED_BYTE, out);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.deleteFramebuffer(fb);
    gl.deleteTexture(t);
    const heat = b.images.heat.data;
    let n = 0, w2 = 0, w8 = 0, sum = 0, mx = 0;
    for (let y = 0; y < b.H; y++) {
      for (let x = 0; x < b.W; x++) {
        const a = out[4 * ((b.H - 1 - y) * b.W + x)], e = heat[4 * (y * b.W + x)];
        if (a === 0 && e === 0) continue;
        const d = Math.abs(a - e);
        n++; sum += d; if (d > mx) mx = d; if (d <= 2) w2++; if (d <= 8) w8++;
      }
    }
    this.dirty = true;
    return { n, within2: n ? w2 / n : 1, within8: n ? w8 / n : 1, meanAbs: n ? sum / n : 0, maxAbs: mx };
  }

  /** CPU evaluation at one pixel (tooltips). */
  inspect(u, v) {
    const b = this.b, p = Math.floor(v) * b.W + Math.floor(u);
    const id = b.lab[p];
    const out = { id, index: b.labelToIndex[id], Y: b.Y[p] };
    const row = this.rows && this.rows.find((r) => r.id === id);
    if (row && row.hasRes && b.images.normals) {
      const nd = b.images.normals.data;
      let n = [nd[4 * p] / 255 * 2 - 1, nd[4 * p + 1] / 255 * 2 - 1, nd[4 * p + 2] / 255 * 2 - 1];
      const L = Math.hypot(...n) || 1; n = n.map((x) => x / L);
      const l = this.opts.light;
      const s = Math.max(0, n[0] * l[0] + n[1] * l[1] + n[2] * l[2]);
      const x = s * 32, i = Math.min(Math.floor(x), 31), f = x - i;
      const yh = row.lut[i] * (1 - f) + row.lut[i + 1] * f;
      const unc = b.images.unc ? b.images.unc.data[4 * p] / 255 * 45 : 0;
      const ur = unc * Math.PI / 180;
      out.ndotl = s; out.Yhat = yh; out.unc = unc;
      out.z = Math.abs(out.Y - yh) / Math.sqrt(row.sigma ** 2 + (row.slope * ur) ** 2);
    }
    return out;
  }

  destroy() { this.destroyed = true; this.ro.disconnect(); }
}
