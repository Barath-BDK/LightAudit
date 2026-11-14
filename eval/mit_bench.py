"""Real curved-object benchmark on the MIT Intrinsic Images dataset (Grosse et al., ICCV 2009).

20 real objects, each photographed under 10 lamp positions (linear 16-bit, diffuse component), with an object mask
and a ground-truth reflectance image. The lamp was hand-held, so light positions are not calibrated across
objects; the splice test is therefore built inside each object:

  * the object mask is cut into K spatial parts (k-means on pixel coordinates);
  * clean image = all parts under lamp i; spliced image = one part under lamp j != i (same pixels, same geometry);
  * score = per-part "shares the light of the other parts" test (real_bench.lr_scores or the correlation drop).

Normals come from the pretrained estimators run on the mean-over-lamps image (evenly lit).

    python eval/mit_bench.py prepare         # normals for all objects -> data/mit_intrinsic/<obj>/prep.npz
    python eval/mit_bench.py bench
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from eval.real_bench import ESTIMATORS, ang, auc, lr_scores  # noqa: E402

DATA = ROOT / "data" / "mit_intrinsic"
NL = 10


def objects() -> list[str]:
    return sorted(p.name for p in DATA.iterdir() if (p / "light10.png").exists())


def read(obj: str, name: str) -> np.ndarray:
    return cv2.imread(str(DATA / obj / f"{name}.png"), cv2.IMREAD_UNCHANGED).astype(np.float32)


def load(obj: str) -> dict:
    """lin[l] (H, W) linear luminance per lamp (scaled so the object's 99th percentile over all lamps is 1), rgb
    display images, mask, reflectance."""
    raw = [read(obj, f"light{l:02d}") for l in range(1, NL + 1)]
    raw = [x if x.ndim == 3 else np.repeat(x[..., None], 3, 2) for x in raw]
    mask = read(obj, "mask") > 0
    scale = np.percentile(np.stack(raw)[:, mask].mean(-1), 99)
    lin = np.stack([x.mean(-1) / scale for x in raw])
    rgb = np.stack([np.clip(x[..., ::-1] / scale, 0, 1) ** (1 / 2.2) for x in raw])  # display RGB in [0, 1]
    refl = read(obj, "reflectance")
    refl = refl.mean(-1) if refl.ndim == 3 else refl
    return dict(lin=lin, rgb=rgb, mask=mask, refl=refl / max(float(np.percentile(refl[mask], 99)), 1e-6))


def prepare(obj: str, up: int = 2) -> Path:
    """Normals of each backend on the mean-over-lamps image (upsampled `up` x for the networks)."""
    from lightaudit import normals as NM
    f = DATA / obj / "prep.npz"
    if f.exists():
        return f
    d = load(obj)
    mean = (np.clip(d["rgb"].mean(0), 0, 1) * 255).astype(np.uint8)
    H, W = mean.shape[:2]
    big = cv2.resize(mean, (W * up, H * up), interpolation=cv2.INTER_CUBIC)
    out, log = {}, []
    for be in ("dsine", "depth_anything"):
        try:
            n = NM._cached_backend(be, big, 60.0, log)
            n = cv2.resize(n, (W, H), interpolation=cv2.INTER_AREA)
            out["normals_" + be] = (n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)).astype(np.float16)
        except Exception as e:
            print(obj, be, "failed:", type(e).__name__, e, flush=True)
    if len(out) == 2:
        n = out["normals_dsine"].astype(np.float32) + out["normals_depth_anything"].astype(np.float32)
        out["normals"] = (n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)).astype(np.float16)
    np.savez_compressed(f, **out)
    print(obj, "prepared:", list(out), flush=True)
    return f


def parts(mask: np.ndarray, k: int = 5, seed: int = 0) -> np.ndarray:
    """Label map: the mask cut into k spatial parts (k-means on pixel coordinates), 0 outside."""
    ys, xs = np.nonzero(mask)
    pts = np.stack([xs, ys], 1).astype(np.float32)
    cv2.setRNGSeed(seed)
    _, lab, _ = cv2.kmeans(pts, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5), 3, cv2.KMEANS_PP_CENTERS)
    out = np.zeros(mask.shape, np.int32)
    out[ys, xs] = lab.ravel() + 1
    return out


def landscapes(obj: str, est: str, nkey: str, k: int = 5, oracle_albedo: bool = False, max_px: int = 1500,
               erode: int = 3, dirs=None) -> dict:
    """S[l, part, D] + per-part info. oracle_albedo divides the image by the ground-truth reflectance first."""
    from lightaudit.grid import coarse_index, eq_dirs
    d = load(obj)
    prep = np.load(DATA / obj / "prep.npz")
    N = prep[nkey].astype(np.float32)
    lab = parts(d["mask"], k)
    dirs = eq_dirs()[coarse_index(4)] if dirs is None else dirs
    inner = cv2.erode(d["mask"].astype(np.uint8), np.ones((2 * erode + 1,) * 2, np.uint8)).astype(bool)
    rng = np.random.default_rng(0)
    fn = ESTIMATORS[est]
    S = np.full((NL, k, len(dirs)), np.nan, np.float32)
    info = []
    for p in range(1, k + 1):
        ys, xs = np.nonzero((lab == p) & inner & (N[..., 2] > 0.05) & (d["refl"] > 0.02))
        if len(ys) > max_px:
            pick = rng.choice(len(ys), max_px, replace=False)
            ys, xs = ys[pick], xs[pick]
        n = N[ys, xs]
        info.append(dict(n_px=len(ys), eig=float(np.linalg.eigvalsh(np.cov(n.T))[0]) if len(ys) > 10 else 0.0))
        if len(ys) < 200:
            continue
        for l in range(NL):
            y = d["lin"][l][ys, xs]
            if oracle_albedo:
                y = y / d["refl"][ys, xs]
            ok = (y > 0.01) & (d["lin"][l][ys, xs] < 0.98)
            if ok.sum() >= 150:
                S[l, p - 1] = fn(n[ok], np.clip(y[ok], 0, None) ** (1 / 2.2), (d["rgb"][l][ys, xs][ok] * 255), dirs)
    return dict(S=S, info=info, dirs=dirs)


def bench(est="ls", nkey="normals_dsine", k=5, score="lr", min_rho=0.3, min_eig=0.0, oracle_albedo=False, n_eff=40.0,
          objs=None, seed=0, verbose=True, cache={}):
    """Within-object splice benchmark, pooled over objects. Returns AUC, TPR at 5/10% FPR, top-1 localisation."""
    rng = np.random.default_rng(seed)
    neg, pos, loc, used = [], [], [], 0
    for obj in (objs or objects()):
        key = (obj, est, nkey, k, oracle_albedo)
        if key not in cache:
            cache[key] = landscapes(obj, est, nkey, k, oracle_albedo)
        L = cache[key]
        S = L["S"]
        rho = np.nanmax(np.where(np.isnan(S), -9, S), 2)
        geom = np.array([i["eig"] >= min_eig for i in L["info"]])
        rel = geom[None] & (rho >= min_rho)
        best = L["dirs"][np.nanargmax(np.where(np.isnan(S), -9, S), 2)]
        for i in range(NL):
            idx = np.flatnonzero(rel[i])
            if len(idx) < 3:
                continue
            used += 1
            Si = S[i, idx]

            def sc_fn(M):
                if score == "lr":
                    a, b, _ = lr_scores(M, n_eff)
                    return a, b
                F = M.sum(0)
                s = [M[q].max() - M[q, int(np.argmax(F - M[q]))] for q in range(len(M))]
                return float(np.max(s)), int(np.argmax(s))

            neg.append(sc_fn(Si)[0])
            for kk, p in enumerate(idx):
                cand = [j for j in range(NL) if j != i and rel[j, p]]
                if not cand:
                    continue
                j = int(rng.choice(cand))
                M = Si.copy()
                M[kk] = S[j, p]
                a, top = sc_fn(M)
                pos.append(a)
                loc.append(top == kk)
    nv, pv = np.array(neg), np.array(pos)
    out = dict(auc=auc(nv, pv), n_neg=len(nv), n_pos=len(pv), loc=float(np.mean(loc)) if loc else float("nan"),
               tpr5=float(np.mean(pv > np.quantile(nv, 0.95))) if len(nv) and len(pv) else float("nan"),
               tpr10=float(np.mean(pv > np.quantile(nv, 0.90))) if len(nv) and len(pv) else float("nan"))
    if verbose:
        tag = f"{est}/{nkey.replace('normals_', '').replace('normals', 'ens')}/k{k}/{score}/rho{min_rho}/eig{min_eig}" + ("/oracle-albedo" if oracle_albedo else "")
        print(f"{tag:52s} AUC {out['auc']:.3f}  TPR@5% {out['tpr5']:.2f}  TPR@10% {out['tpr10']:.2f}  top-1 {out['loc']:.2f}  "
              f"n {out['n_neg']}/{out['n_pos']}", flush=True)
    return out


def part_stats(obj: str, nkey: str, k: int = 5, albedo: str = "none", max_px: int = 1500, erode: int = 3,
               clamp: bool = True, n_clusters: int = 3) -> dict:
    """Sufficient statistics for the shared-material test, per part p, lamp l, direction d and albedo cluster c:
    n, sum s, sum s^2 (lamp-independent) and sum y, sum y^2, sum s*y. albedo: "none" (one cluster), "oracle"
    (divide by the ground-truth reflectance), "chroma" (k-means on chromaticity), "lum" (k-means on the log
    luminance of the image itself: crude albedo proxy for grey paint)."""
    from lightaudit.grid import coarse_index, eq_dirs
    d = load(obj)
    N = np.load(DATA / obj / "prep.npz")[nkey].astype(np.float32)
    lab = parts(d["mask"], k)
    dirs = eq_dirs()[coarse_index(4)].astype(np.float32)
    inner = cv2.erode(d["mask"].astype(np.uint8), np.ones((2 * erode + 1,) * 2, np.uint8)).astype(bool)
    rng = np.random.default_rng(0)
    C = 1 if albedo in ("none", "oracle") else n_clusters
    D = len(dirs)
    st = dict(n=np.zeros((k, C)), A=np.zeros((k, C, D)), B=np.zeros((k, C, D)), Y=np.zeros((NL, k, C)),
              Y2=np.zeros((NL, k, C)), SY=np.zeros((NL, k, C, D)), eig=np.zeros(k), dirs=dirs)
    for p in range(k):
        ys, xs = np.nonzero((lab == p + 1) & inner & (N[..., 2] > 0.05) & (d["refl"] > 0.02))
        if len(ys) > max_px:
            pick = rng.choice(len(ys), max_px, replace=False)
            ys, xs = ys[pick], xs[pick]
        if len(ys) < 200:
            continue
        n = N[ys, xs]
        st["eig"][p] = float(np.linalg.eigvalsh(np.cov(n.T))[0])
        s = dirs @ n.T
        s = np.maximum(s, 0) if clamp else s  # (D, N)
        for l in range(NL):
            y = d["lin"][l][ys, xs].astype(np.float64)
            if albedo == "oracle":
                y = y / d["refl"][ys, xs]
            if C == 1:
                cl = np.zeros(len(ys), int)
            elif albedo == "chroma":
                x = d["rgb"][l][ys, xs].astype(np.float32) + 0.02
                cl = _kmeans((x[:, :2] / x.sum(1, keepdims=True)), C)
            else:  # "lum": clusters of the pixel's own brightness rank among neighbours of similar shading
                cl = _kmeans(np.log(1e-3 + y)[:, None].astype(np.float32), C)
            for c in range(C):
                m = cl == c
                if l == 0 or C > 1:
                    pass
                st["Y"][l, p, c] = y[m].sum()
                st["Y2"][l, p, c] = (y[m] ** 2).sum()
                st["SY"][l, p, c] = s[:, m] @ y[m]
                if C == 1:
                    st["n"][p, c], st["A"][p, c], st["B"][p, c] = m.sum(), s[:, m].sum(1), (s[:, m] ** 2).sum(1)
        if C > 1:  # cluster membership depends on the lamp, so the s-sums do too: store them per lamp
            st.setdefault("nL", np.zeros((NL, k, C)))
            st.setdefault("AL", np.zeros((NL, k, C, D)))
            st.setdefault("BL", np.zeros((NL, k, C, D)))
            for l in range(NL):
                y = d["lin"][l][ys, xs].astype(np.float64)
                x = d["rgb"][l][ys, xs].astype(np.float32) + 0.02
                cl = _kmeans((x[:, :2] / x.sum(1, keepdims=True)), C) if albedo == "chroma" else _kmeans(np.log(1e-3 + y)[:, None].astype(np.float32), C)
                for c in range(C):
                    m = cl == c
                    st["nL"][l, p, c], st["AL"][l, p, c], st["BL"][l, p, c] = m.sum(), s[:, m].sum(1), (s[:, m] ** 2).sum(1)
    return st


def _kmeans(x, k):
    cv2.setRNGSeed(0)
    _, lab, cen = cv2.kmeans(np.ascontiguousarray(x, np.float32), k, None,
                             (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1e-4), 2, cv2.KMEANS_PP_CENTERS)
    order = np.argsort(cen.sum(1))  # stable cluster ids (sorted by centre) so clusters match across parts
    return np.argsort(order)[lab.ravel()]


def shared_scores(n, A, B, Y, Y2, SY, n_eff=40.0, df=4):
    """Shared-material test for one image. Inputs are per-part sums (P, D) / (P,) for a single albedo cluster.

    For each part k: fit ONE shading model y = a*s(l) + b on the pooled pixels of the other parts (best light l*),
    predict part k with it, and compare that residual with part k's own best fit (own light, own a and b).
    T_k = log(RSS_shared / RSS_own); n_eff * T_k is referred to chi-square(df); Holm over parts."""
    from scipy.stats import chi2
    P = len(n)
    T = np.zeros(P)
    for k in range(P):
        o = np.arange(P) != k
        nn, a_, b_, y_, y2_, sy_ = n[o].sum(), A[o].sum(0), B[o].sum(0), Y[o].sum(), Y2[o].sum(), SY[o].sum(0)
        var_s = b_ - a_ ** 2 / nn
        cov = sy_ - a_ * y_ / nn
        gain = np.where(var_s > 1e-9, cov / np.maximum(var_s, 1e-9), 0.0)
        rss = (y2_ - y_ ** 2 / nn) - np.where(gain > 0, gain * cov, 0.0)  # non-negative gain only
        j = int(np.argmin(rss))
        g = max(gain[j], 0.0)
        off = (y_ - g * a_[j]) / nn
        rss_shared = Y2[k] + g * g * B[k, j] + n[k] * off * off - 2 * g * SY[k, j] - 2 * off * Y[k] + 2 * g * off * A[k, j]
        vs = B[k] - A[k] ** 2 / n[k]
        cv = SY[k] - A[k] * Y[k] / n[k]
        own = (Y2[k] - Y[k] ** 2 / n[k]) - np.where((vs > 1e-9) & (cv > 0), cv ** 2 / np.maximum(vs, 1e-9), 0.0)
        T[k] = np.log(max(rss_shared, 1e-12) / max(float(own.min()), 1e-12))
    p = chi2.sf(n_eff * np.maximum(T, 0), df)
    order = np.argsort(p)
    adj = p[order[0]] * P
    return float(-np.log10(max(min(adj, 1.0), 1e-300))), int(order[0]), T


def bench_shared(nkey="normals_dsine", k=5, albedo="none", clamp=True, n_eff=40.0, objs=None, seed=0, verbose=True,
                 cache={}, per_object=False):
    """Within-object splice benchmark with the shared-material test (single albedo cluster variants)."""
    rng = np.random.default_rng(seed)
    neg, pos, loc, rows = [], [], [], []
    for obj in (objs or objects()):
        key = (obj, nkey, k, albedo, clamp)
        if key not in cache:
            cache[key] = part_stats(obj, nkey, k, albedo, clamp=clamp)
        st = cache[key]
        ok = np.flatnonzero(st["n"][:, 0] >= 200)
        if len(ok) < 3:
            continue
        n, A, B = st["n"][ok, 0], st["A"][ok, 0], st["B"][ok, 0]
        on, op = [], []
        for i in range(NL):
            Y, Y2, SY = st["Y"][i, ok, 0], st["Y2"][i, ok, 0], st["SY"][i, ok, 0]
            on.append(shared_scores(n, A, B, Y, Y2, SY, n_eff)[0])
            for kk in range(len(ok)):
                j = int(rng.choice([x for x in range(NL) if x != i]))
                Yj, Y2j, SYj = Y.copy(), Y2.copy(), SY.copy()
                Yj[kk], Y2j[kk], SYj[kk] = st["Y"][j, ok[kk], 0], st["Y2"][j, ok[kk], 0], st["SY"][j, ok[kk], 0]
                a, top, _ = shared_scores(n, A, B, Yj, Y2j, SYj, n_eff)
                op.append(a)
                loc.append(top == kk)
        neg += on
        pos += op
        rows.append((obj, auc(on, op)))
    nv, pv = np.array(neg), np.array(pos)
    out = dict(auc=auc(nv, pv), tpr5=float(np.mean(pv > np.quantile(nv, 0.95))), tpr10=float(np.mean(pv > np.quantile(nv, 0.90))),
               loc=float(np.mean(loc)), n_neg=len(nv), n_pos=len(pv), per_object=rows)
    if verbose:
        tag = f"shared/{nkey.replace('normals_', '').replace('normals', 'ens')}/k{k}/albedo-{albedo}/{'clamp' if clamp else 'sh1'}"
        print(f"{tag:52s} AUC {out['auc']:.3f}  TPR@5% {out['tpr5']:.2f}  TPR@10% {out['tpr10']:.2f}  top-1 {out['loc']:.2f}  "
              f"n {out['n_neg']}/{out['n_pos']}", flush=True)
        if per_object:
            print("   per object:", "  ".join(f"{o} {a:.2f}" for o, a in rows), flush=True)
    return out


# ----------------------------------------------------------------------- shared material + paint levels
from lightaudit.residual import retinex_albedo  # noqa: E402


def pixel_data(obj: str, nkey: str, k: int = 5, max_px: int = 1200, erode: int = 3, n_seg: int = 150, clamp=True,
               ret_thr: float = 0.10) -> dict:
    """Per part: s matrix (D, N), per-lamp luminance y[l] (N,), per-lamp segment ids, true reflectance."""
    from skimage.segmentation import slic
    from lightaudit.grid import coarse_index, eq_dirs
    d = load(obj)
    N = np.load(DATA / obj / "prep.npz")[nkey].astype(np.float32)
    lab = parts(d["mask"], k)
    dirs = eq_dirs()[coarse_index(4)].astype(np.float32)
    inner = cv2.erode(d["mask"].astype(np.uint8), np.ones((2 * erode + 1,) * 2, np.uint8)).astype(bool)
    segs = [slic(d["rgb"][l], n_segments=n_seg, compactness=8, mask=d["mask"], start_label=1) for l in range(NL)]
    ret = [retinex_albedo(d["lin"][l], d["mask"], ret_thr) for l in range(NL)]
    rng = np.random.default_rng(0)
    out = []
    for p in range(1, k + 1):
        ys, xs = np.nonzero((lab == p) & inner & (N[..., 2] > 0.05) & (d["refl"] > 0.02))
        if len(ys) > max_px:
            pick = rng.choice(len(ys), max_px, replace=False)
            ys, xs = ys[pick], xs[pick]
        if len(ys) < 200:
            continue
        s = dirs @ N[ys, xs].T
        out.append(dict(S=np.maximum(s, 0) if clamp else s, y=np.stack([d["lin"][l][ys, xs] for l in range(NL)]).astype(np.float64),
                        ret=np.stack([ret[l][ys, xs] for l in range(NL)]).astype(np.float64), ys=ys, xs=xs, pid=p,
                        seg=np.stack([segs[l][ys, xs] + 100000 * p for l in range(NL)]), refl=d["refl"][ys, xs].astype(np.float64)))
    return dict(parts=out, dirs=dirs, lin=d["lin"], mask=d["mask"], lab=lab)


def _fit(S, y):
    """Best light for y ~ a*s + b with a >= 0: returns (index, a, b, rss per direction)."""
    n = len(y)
    A, B, SY, Y = S.sum(1), (S * S).sum(1), S @ y, y.sum()
    var = B - A * A / n
    cov = SY - A * Y / n
    gain = np.where((var > 1e-9) & (cov > 0), cov / np.maximum(var, 1e-9), 0.0)
    rss = (y @ y - Y * Y / n) - gain * cov
    j = int(np.argmin(rss))
    return j, float(gain[j]), float((Y - gain[j] * A[j]) / n), rss


def _seg_levels(y, pred, seg, levels):
    """Each segment takes the paint level (multiplicative) that best explains it. Returns per-pixel alpha."""
    alpha = np.ones(len(y))
    for g in np.unique(seg):
        m = seg == g
        err = [(((y[m] / a) - pred[m]) ** 2).sum() for a in levels]
        alpha[m] = levels[int(np.argmin(err))]
    return alpha


def _learn_levels(y, pred, seg, C):
    """Paint levels from per-segment medians of y / prediction (k-means in log space), normalised to median 1."""
    q = np.array([np.median(y[seg == g] / np.maximum(pred[seg == g], 1e-3)) for g in np.unique(seg)])
    q = np.log(np.clip(q, 0.05, 20)).astype(np.float32)[:, None]
    if C == 1 or len(q) < C + 1:
        return np.array([1.0])
    cv2.setRNGSeed(0)
    _, _, cen = cv2.kmeans(q, C, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1e-4), 2, cv2.KMEANS_PP_CENTERS)
    lv = np.exp(np.sort(cen.ravel()))
    return lv / np.median(lv)


def levels_scores(P, lamps, C=3, iters=3, albedo="levels", n_eff=40.0, alb=None):
    """Shared-material test with jointly estimated paint levels. P = list of part dicts, lamps[p] = lamp of part p.

    For part k: (1) on the other parts, alternate between fitting one shading model y/alpha ~ a*s(l) + b and
    re-estimating C paint levels with one level per segment; (2) part k under that model, each of its segments free
    to pick a level -> RSS_shared; (3) part k with its own light and gain/offset, same levels -> RSS_own.
    albedo="oracle" divides by the true reflectance instead; "none" uses a single level."""
    from scipy.stats import chi2
    T = np.zeros(len(P))
    Y = [p["y"][l] / (p["refl"] if albedo == "oracle" else p["ret"][l] if albedo == "retinex" else 1.0) for p, l in zip(P, lamps)]
    if alb is not None:  # per-part albedo computed on the actual composite image
        Y = [p["y"][l] / a for p, l, a in zip(P, lamps, alb)]
    G = [p["seg"][l] for p, l in zip(P, lamps)]
    Cn = C if albedo == "levels" else 1
    for k in range(len(P)):
        o = [q for q in range(len(P)) if q != k]
        S, y, seg = np.concatenate([P[q]["S"] for q in o], 1), np.concatenate([Y[q] for q in o]), np.concatenate([G[q] for q in o])
        alpha, levels = np.ones(len(y)), np.array([1.0])
        for it in range(iters if Cn > 1 else 1):
            j, a, b, _ = _fit(S, y / alpha)
            if Cn > 1:
                pred = a * S[j] + b
                levels = _learn_levels(y, pred, seg, Cn)
                alpha = _seg_levels(y, pred, seg, levels)
        j, a, b, _ = _fit(S, y / alpha)
        Sk, yk, gk = P[k]["S"], Y[k], G[k]
        pred = a * Sk[j] + b
        ak = _seg_levels(yk, pred, gk, levels)
        rss_shared = (((yk / ak) - pred) ** 2).sum()
        own_alpha = ak
        for it in range(2 if Cn > 1 else 1):
            jo, ao, bo, rss = _fit(Sk, yk / own_alpha)
            if Cn > 1:
                own_alpha = _seg_levels(yk, ao * Sk[jo] + bo, gk, levels)
        jo, ao, bo, rss = _fit(Sk, yk / own_alpha)
        T[k] = np.log(max(rss_shared, 1e-12) / max(float(rss.min()), 1e-12))
    pv = chi2.sf(n_eff * np.maximum(T, 0), 4)
    kbest = int(np.argmin(pv))
    return float(-np.log10(max(min(pv[kbest] * len(P), 1.0), 1e-300))), kbest, T


def bench_levels(nkey="normals_depth_anything", k=4, C=3, albedo="levels", objs=None, seed=0, verbose=True, cache={},
                 n_seg=150, lamps_per_obj=NL, clamp=True, ret_thr=0.10):
    rng = np.random.default_rng(seed)
    neg, pos, loc, rows = [], [], [], []
    for obj in (objs or objects()):
        key = (obj, nkey, k, n_seg, clamp, ret_thr)
        if key not in cache:
            cache[key] = pixel_data(obj, nkey, k, n_seg=n_seg, clamp=clamp, ret_thr=ret_thr)
        P = cache[key]["parts"]
        if len(P) < 3:
            continue
        on, op = [], []
        for i in range(lamps_per_obj):
            on.append(levels_scores(P, [i] * len(P), C, albedo=albedo)[0])
            for kk in range(len(P)):
                lamps = [i] * len(P)
                lamps[kk] = int(rng.choice([x for x in range(NL) if x != i]))
                a, top, _ = levels_scores(P, lamps, C, albedo=albedo)
                op.append(a)
                loc.append(top == kk)
        neg += on
        pos += op
        rows.append((obj, auc(on, op)))
    nv, pv = np.array(neg), np.array(pos)
    out = dict(auc=auc(nv, pv), tpr5=float(np.mean(pv > np.quantile(nv, 0.95))), tpr10=float(np.mean(pv > np.quantile(nv, 0.90))),
               loc=float(np.mean(loc)), n_neg=len(nv), n_pos=len(pv), per_object=rows)
    if verbose:
        tag = f"levels/{nkey.replace('normals_', '').replace('normals', 'ens')}/k{k}/C{C}/albedo-{albedo}/seg{n_seg}/thr{ret_thr}"
        print(f"{tag:52s} AUC {out['auc']:.3f}  TPR@5% {out['tpr5']:.2f}  TPR@10% {out['tpr10']:.2f}  top-1 {out['loc']:.2f}  "
              f"n {out['n_neg']}/{out['n_pos']}", flush=True)
    return out


def lamp_dirs(P):
    """Best single light per lamp for the whole object (oracle albedo): only used to bin splices by angle."""
    S = np.concatenate([p["S"] for p in P], 1)
    return np.array([_fit(S, np.concatenate([p["y"][l] / p["refl"] for p in P]))[0] for l in range(NL)])


def angle_curve(nkey="normals_depth_anything", k=4, albedo="oracle", C=1, bins=((0, 25), (25, 50), (50, 80), (80, 181)),
                ret_thr=0.10, cache={}):
    """Detection rate against the lighting-angle difference of the splice (threshold = 10% false alarms on the
    clean images of the same run). Angles come from whole-object light estimates, so they are approximate."""
    neg, rows = [], []
    for obj in objects():
        key = (obj, nkey, k, 150, True, ret_thr)
        if key not in cache:
            cache[key] = pixel_data(obj, nkey, k, ret_thr=ret_thr)
        P, dirs = cache[key]["parts"], cache[key]["dirs"]
        if len(P) < 3:
            continue
        ld = dirs[lamp_dirs(P)]
        for i in range(NL):
            neg.append(levels_scores(P, [i] * len(P), C, albedo=albedo)[0])
            for kk in range(len(P)):
                for j in range(NL):
                    if j == i or (i + j + kk) % 3:  # a third of all (i, j, part) triples
                        continue
                    lamps = [i] * len(P)
                    lamps[kk] = j
                    rows.append((float(ang(ld[i], ld[j])), levels_scores(P, lamps, C, albedo=albedo)[0]))
    thr = np.quantile(neg, 0.90)
    rows = np.array(rows)
    print(f"angle curve ({nkey}, albedo {albedo}, k={k}); threshold at 10% false alarms, {len(neg)} clean images")
    for lo, hi in bins:
        m = (rows[:, 0] >= lo) & (rows[:, 0] < hi)
        if m.sum():
            print(f"  {lo:3d}-{hi:3d} deg: detected {np.mean(rows[m, 1] > thr):.2f}  AUC {auc(neg, rows[m, 1]):.2f}  (n = {int(m.sum())})", flush=True)


def composite_albedo(Dd, lamps, thr, guard=False):
    """Retinex albedo of the composite image itself (part p taken from lamp lamps[p]), sampled at each part."""
    comp = np.zeros_like(Dd["lin"][0])
    for p, l in zip(Dd["parts"], lamps):
        m = Dd["lab"] == p["pid"]
        comp[m] = Dd["lin"][l][m]
    rest = Dd["mask"] & ~np.isin(Dd["lab"], [p["pid"] for p in Dd["parts"]])
    comp[rest] = Dd["lin"][lamps[0]][rest]
    r = retinex_albedo(comp, Dd["mask"], thr, Dd["lab"] if guard else None)
    return [r[p["ys"], p["xs"]] for p in Dd["parts"]]


def bench_composite(nkey="normals_depth_anything", k=4, thr=0.10, seed=0, cache={}, guard=False, albedo="retinex", angle_bins=((0, 25), (25, 50), (50, 80), (80, 181)),
                    verbose=True, objs=None):
    """Shared-material test with Retinex albedo computed on each composite image (the honest single-image case).
    Also reports detection by lighting-angle bin (angles from whole-object light estimates, approximate)."""
    rng = np.random.default_rng(seed)
    neg, pos, loc, angs, per = [], [], [], [], []
    for obj in (objs or objects()):
        key = (obj, nkey, k, 150, True, thr)
        if key not in cache:
            cache[key] = pixel_data(obj, nkey, k, ret_thr=thr)
        Dd = cache[key]
        P = Dd["parts"]
        if len(P) < 3:
            continue
        ld = Dd["dirs"][lamp_dirs(P)]
        on, op = [], []
        for i in range(NL):
            lamps = [i] * len(P)
            on.append(levels_scores(P, lamps, 1, albedo="none", alb=composite_albedo(Dd, lamps, thr, guard) if albedo == "retinex" else None)[0])
            for kk in range(len(P)):
                for j in rng.choice([x for x in range(NL) if x != i], 2, replace=False):
                    lamps = [i] * len(P)
                    lamps[kk] = int(j)
                    a, top, _ = levels_scores(P, lamps, 1, albedo="none", alb=composite_albedo(Dd, lamps, thr, guard) if albedo == "retinex" else None)
                    op.append(a)
                    loc.append(top == kk)
                    angs.append(float(ang(ld[i], ld[int(j)])))
        neg += on
        pos += op
        per.append((obj, auc(on, op)))
    nv, pv, angs = np.array(neg), np.array(pos), np.array(angs)
    t10, t5 = np.quantile(nv, 0.90), np.quantile(nv, 0.95)
    out = dict(auc=auc(nv, pv), tpr5=float(np.mean(pv > t5)), tpr10=float(np.mean(pv > t10)), loc=float(np.mean(loc)),
               per_object=per, neg=nv, pos=pv, angs=angs)
    if verbose:
        print(f"composite-{albedo}{'-guarded' if guard else ''}/{nkey.replace('normals_', '')}/k{k}/thr{thr}: AUC {out['auc']:.3f}  TPR@5% {out['tpr5']:.2f}  "
              f"TPR@10% {out['tpr10']:.2f}  top-1 {out['loc']:.2f}  n {len(nv)}/{len(pv)}", flush=True)
        for lo, hi in angle_bins:
            m = (angs >= lo) & (angs < hi)
            if m.sum():
                print(f"    {lo:3d}-{hi:3d} deg: detected at 10% FPR {np.mean(pv[m] > t10):.2f}   AUC {auc(nv, pv[m]):.2f}   n {int(m.sum())}", flush=True)
        print("    per object:", "  ".join(f"{o} {a:.2f}" for o, a in per), flush=True)
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "bench"
    if cmd == "guard":
        bench_composite(albedo="none")
        for thr in (0.10, 0.05, 0.20):
            bench_composite(guard=True, thr=thr)
        sys.exit(0)
    if cmd == "composite":
        for nk in ("normals_depth_anything", "normals_dsine", "normals"):
            bench_composite(nk)
        sys.exit(0)
    if cmd == "angle":
        angle_curve(albedo=sys.argv[2] if len(sys.argv) > 2 else "oracle")
        sys.exit(0)
    if cmd == "retinex":
        for thr in (0.05, 0.10, 0.20):
            bench_levels(albedo="retinex", C=1, ret_thr=thr)
        sys.exit(0)
    if cmd == "levels":
        for alb, C in (("none", 1), ("oracle", 1), ("levels", 2), ("levels", 3), ("levels", 4)):
            bench_levels(albedo=alb, C=C)
        sys.exit(0)
    if cmd == "shared":
        for nkey in ("normals_dsine", "normals_depth_anything", "normals"):
            bench_shared(nkey, albedo="none")
            bench_shared(nkey, albedo="oracle")
        bench_shared("normals_depth_anything", albedo="none", clamp=False)
        bench_shared("normals_depth_anything", albedo="oracle", k=4)
        bench_shared("normals_depth_anything", albedo="oracle", k=8, per_object=True)
        sys.exit(0)
    if cmd == "prepare":
        for o in objects():
            prepare(o)
    else:
        for nkey in ("normals_dsine", "normals_depth_anything", "normals"):
            for est in ("ls", "sh1", "ls_alb"):
                bench(est, nkey)
        bench("ls", "normals_dsine", oracle_albedo=True)
        bench("ls", "normals_dsine", score="drop")
