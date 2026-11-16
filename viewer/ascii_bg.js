// Gallery hero background: a small scene lit by ONE orbiting light, drawn as characters. Shading and cast shadows
// both follow the same light, which is exactly what LightAudit checks. Ray-traced per character cell (spheres on a
// ground plane), 10 steps per second, paused off screen; one still frame when the viewer prefers reduced motion.

const CHARS = ' .:-=+*#%';
const SPHERES = [  // x, y, z, r (y up, camera at the origin looking down -z); weighted to the right of the frame
  [2.4, 1.35, -5.6, 1.35], [4.9, 0.8, -6.6, 0.8], [3.6, 0.5, -3.9, 0.5], [6.6, 1.5, -9.5, 1.5], [0.9, 0.55, -7.4, 0.55],
];
const GROUND = 0;  // plane y = 0
const CAM_Y = 1.5, TILT = -0.16;

function hitSphere(o, d, s) {
  const ox = o[0] - s[0], oy = o[1] - s[1], oz = o[2] - s[2];
  const b = ox * d[0] + oy * d[1] + oz * d[2];
  const c = ox * ox + oy * oy + oz * oz - s[3] * s[3];
  const h = b * b - c;
  if (h < 0) return -1;
  const t = -b - Math.sqrt(h);
  return t > 1e-3 ? t : -1;
}

function shade(d, L) {
  const o = [0, CAM_Y, 0];
  let tMin = Infinity, hit = -1;
  SPHERES.forEach((s, k) => { const t = hitSphere(o, d, s); if (t > 0 && t < tMin) { tMin = t; hit = k; } });
  let p, n;
  if (hit >= 0) {
    p = [o[0] + d[0] * tMin, o[1] + d[1] * tMin, o[2] + d[2] * tMin];
    const s = SPHERES[hit];
    n = [(p[0] - s[0]) / s[3], (p[1] - s[1]) / s[3], (p[2] - s[2]) / s[3]];
  } else if (d[1] < -1e-4) {
    const t = (GROUND - o[1]) / d[1];
    p = [o[0] + d[0] * t, GROUND, o[2] + d[2] * t];
    n = [0, 1, 0];
    if (p[2] < -26) return null;  // the floor ends in the distance
  } else {
    return null;  // nothing hit: empty sky
  }
  let lam = Math.max(0, n[0] * L[0] + n[1] * L[1] + n[2] * L[2]);
  if (lam > 0) {  // cast shadow: anything between the point and the light
    const q = [p[0] + n[0] * 1e-3, p[1] + n[1] * 1e-3, p[2] + n[2] * 1e-3];
    if (SPHERES.some((s, k) => k !== hit && hitSphere(q, L, s) > 0)) lam = 0;
  }
  const floorFade = hit >= 0 ? 1 : Math.max(0, 1 + p[2] / 26);
  return [Math.min(1, (hit >= 0 ? 0.16 : 0.07) + 0.9 * lam), floorFade];  // [light, how much of it to draw]; objects keep a little ambient
}

export function asciiBackground(canvas, { cell = 10, fps = 10, onLight } = {}) {
  const ctx = canvas.getContext('2d');
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let cols = 0, rows = 0, atlas = null, dpr = 1, raf = 0, last = 0, visible = true;
  const css = getComputedStyle(document.documentElement);
  let ember = "#ff8a3d", dim = "#85858b", paper = false;  // re-read from the theme in build()

  function mix(a, b, k) {  // two #rrggbb colours
    const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16)), pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
    return `rgb(${pa.map((v, i) => Math.round(v + (pb[i] - v) * k)).join(',')})`;
  }

  function build() {
    ember = css.getPropertyValue("--accent").trim() || "#ff8a3d";
    paper = document.documentElement.dataset.theme === "light";
    dim = css.getPropertyValue(paper ? "--text-2" : "--text-3").trim() || "#85858b";  // darker ink on paper
    dpr = Math.min(2, window.devicePixelRatio || 1);
    const { width, height } = canvas.getBoundingClientRect();
    canvas.width = Math.max(1, Math.round(width * dpr));
    canvas.height = Math.max(1, Math.round(height * dpr));
    cols = Math.ceil(width / cell);
    rows = Math.ceil(height / cell);
    // atlas: every character in every brightness colour, drawn once
    const c = cell * dpr;
    atlas = document.createElement('canvas');
    atlas.width = c * CHARS.length;
    atlas.height = c;
    const pen = atlas.getContext('2d');
    const mono = css.getPropertyValue('--mono').trim() || 'monospace';
    pen.font = `500 ${Math.round(c * 1.05)}px ${mono}`;
    pen.textAlign = 'center';
    pen.textBaseline = 'middle';
    [...CHARS].forEach((ch, i) => {
      const k = i / (CHARS.length - 1);
      // screen: brightness is light (dim grey to ember). Paper: ink is shadow (thin ember on lit faces, dense dark ink in shade)
      pen.fillStyle = paper ? mix(ember.startsWith('#') ? ember : '#b4470f', dim.startsWith('#') ? dim : '#5c5347', Math.pow(k, 0.8))
        : mix(dim.startsWith('#') ? dim : '#85858b', ember.startsWith('#') ? ember : '#ff8a3d', Math.pow(k, 1.6));
      pen.globalAlpha = paper ? 0.6 + 0.4 * k : 0.35 + 0.65 * k;
      pen.fillText(ch, i * c + c / 2, c / 2);
    });
  }

  function draw(t) {
    const az = (t * 0.00012 + 2.2) % (2 * Math.PI) - Math.PI;  // one turn in about 52 s, starting lit from the front left
    const el = 0.48;  // low sun: long cast shadows
    const L = [Math.cos(el) * Math.sin(az), Math.sin(el), Math.cos(el) * Math.cos(az)];
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const c = cell * dpr, aspect = cols / rows * 0.5, f = 1.0;
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const u = ((x + 0.5) / cols * 2 - 1) * aspect * 1.1, v = 1 - (y + 0.5) / rows * 2;
        let d = [u, v * 0.62 + TILT, -f];
        const m = Math.hypot(d[0], d[1], d[2]);
        d = [d[0] / m, d[1] / m, d[2] / m];
        const hitv = shade(d, L);
        if (!hitv) continue;
        const [s, fade] = hitv;
        const ink = (paper ? Math.max(0.12, 1 - s) : s) * fade;  // on paper the ink density follows darkness
        const k = Math.min(CHARS.length - 1, Math.round(ink * (CHARS.length - 1)));
        if (k > 0) ctx.drawImage(atlas, k * c, 0, c, c, x * c, y * c, c, c);
      }
    }
    if (onLight) onLight(az * 180 / Math.PI, el * 180 / Math.PI);
  }

  function loop(now) {
    raf = requestAnimationFrame(loop);
    if (!visible || document.hidden || now - last < 1000 / fps) return;
    last = now;
    draw(now);
  }

  build();
  new ResizeObserver(() => { build(); draw(last || 9000); }).observe(canvas);
  new MutationObserver(() => { build(); draw(last || 9000); }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; }).observe(canvas);
  if (reduce) draw(9000);
  else raf = requestAnimationFrame(loop);
  return () => cancelAnimationFrame(raf);
}
