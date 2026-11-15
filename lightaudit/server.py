"""FastAPI server (BUILD_SPEC 13.2): serves the viewer, bundles, docs and results read-only, plus a small API.

    GET  /                  -> redirect to /viewer/index.html
    GET  /api/health        -> {status, version, backends}
    POST /api/audit         -> multipart (image, optional roi, normals, regions, fov) -> {job_id}
    GET  /api/jobs/{id}     -> {status: queued|running|done|error, progress, stage, bundle, log}
    POST /api/attack        -> JSON {bundle, region, variants, sigma_att} -> {bundle, results: [...]}

Binds to 127.0.0.1 by default. Uploads are limited to 15 MB, filenames are sanitised (only the validated image
format decides the stored extension), bundle names must match ^[A-Za-z0-9_-]+$. Audits run one at a time in a
background worker thread (they are CPU-heavy); attacks run in the request's worker thread.
"""
from __future__ import annotations

import io
import json
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import numpy as np
from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import ROOT, Config

BUNDLES = ROOT / "bundles"
UPLOADS = ROOT / "data" / "uploads"
MAX_UPLOAD = 15 * 1024 * 1024
NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
JOB_RE = re.compile(r"^[0-9a-f]{32}$")
NORMAL_BACKENDS = {"dsine", "stablenormal", "marigold", "depth_anything"}
REGION_BACKENDS = {"sam", "slic"}
ATTACK_VARIANTS = ("T1", "T3a", "T4")
STATIC = {"/viewer": ROOT / "viewer", "/bundles": BUNDLES, "/docs": ROOT / "docs",
          "/results": ROOT / "data" / "results", "/data/results": ROOT / "data" / "results"}
STAGES = ["estimating surface normals", "proposing regions", "estimating per-region light directions"]

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lightaudit-audit")
_bundle_locks: dict[str, threading.Lock] = {}


# ----------------------------------------------------------------------------------------------- helpers
def check_bundle_name(name: str) -> str:
    if not isinstance(name, str) or not NAME_RE.fullmatch(name) or len(name) > 100:
        raise ValueError("bundle names may only contain letters, digits, '_' and '-'")
    return name


def sanitize_stem(filename: str | None) -> str:
    stem = Path(str(filename or "upload")).name.rsplit(".", 1)[0]
    stem = re.sub(r"[^A-Za-z0-9_\-]+", "_", stem).strip("_-")[:40]
    return stem or "upload"


def _decode_image(data: bytes) -> tuple[str, tuple[int, int]]:
    """Validates uploaded bytes as an image; returns (extension, size)."""
    from PIL import Image
    with Image.open(io.BytesIO(data)) as im:
        im.verify()
    with Image.open(io.BytesIO(data)) as im:
        fmt, size = (im.format or "PNG").upper(), im.size
    ext = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "BMP": ".bmp", "TIFF": ".tif"}.get(fmt)
    if ext is None:
        raise ValueError(f"unsupported image format {fmt}")
    return ext, size


def _job_update(job_id: str, **kw) -> None:
    with _jobs_lock:
        _jobs[job_id].update(kw)


def _job_log(job_id: str, msg: str) -> None:
    with _jobs_lock:
        _jobs[job_id]["log"].append(msg)


# ----------------------------------------------------------------------------------------------- audit jobs
def _run_audit_job(job_id: str, image: Path, roi: Path | None, normals: str, regions: str, fov: float,
                   name: str, title: str) -> None:
    from .cli import audit_image
    _job_update(job_id, status="running", started=time.time())

    def progress(msg: str):
        _job_log(job_id, msg)
        if msg in STAGES:
            _job_update(job_id, stage=msg, progress=round((STAGES.index(msg) + 0.5) / (len(STAGES) + 1), 2))

    try:
        d = audit_image(image, name=name, roi=roi, regions=regions, normals=normals, fov=fov, title=title,
                        progress=progress)
        try:
            m = json.loads((d / "manifest.json").read_text())
            for line in m.get("backends_log", []):
                _job_log(job_id, line)
            _job_log(job_id, f"verdict: {m['fusion']['verdict']} (a flag means: send for human review)")
        except (OSError, KeyError, ValueError):
            pass
        _job_update(job_id, status="done", progress=1.0, stage="done", bundle=d.name, finished=time.time())
    except Exception as e:  # report the failure to the client, keep the server alive
        _job_log(job_id, f"ERROR: {type(e).__name__}: {e}")
        _job_update(job_id, status="error", stage="error", error=f"{type(e).__name__}: {e}", finished=time.time())


def submit_audit(data: bytes, filename: str | None, roi: bytes | None = None, normals: str = "dsine,stablenormal",
                 regions: str = "sam", fov: float = 60.0) -> str:
    """Validates an upload, stores it under data/uploads/<job>/ and queues the audit. Returns the job id."""
    if len(data) > MAX_UPLOAD or (roi is not None and len(roi) > MAX_UPLOAD):
        raise OverflowError("upload larger than 15 MB")
    if not data:
        raise ValueError("empty upload")
    toks = [t.strip() for t in (normals or "").split(",") if t.strip()]
    if not toks or any(t not in NORMAL_BACKENDS for t in toks):
        raise ValueError(f"normals must be a comma list of {sorted(NORMAL_BACKENDS)}")
    if regions not in REGION_BACKENDS:
        raise ValueError(f"regions must be one of {sorted(REGION_BACKENDS)}")
    if not 20.0 <= float(fov) <= 120.0:
        raise ValueError("fov must be between 20 and 120 degrees")
    ext, _ = _decode_image(data)
    job_id = uuid.uuid4().hex
    folder = UPLOADS / job_id
    folder.mkdir(parents=True, exist_ok=True)
    stem = sanitize_stem(filename)
    img_path = folder / f"{stem}{ext}"
    img_path.write_bytes(data)
    roi_path = None
    if roi:
        rext, _ = _decode_image(roi)
        roi_path = folder / f"roi{rext}"
        roi_path.write_bytes(roi)
    name = "user_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    with _jobs_lock:
        _jobs[job_id] = dict(status="queued", progress=0.0, stage="queued", bundle=None, log=[], created=time.time(),
                             name=name, error=None)
    _executor.submit(_run_audit_job, job_id, img_path, roi_path, ",".join(toks), regions, float(fov), name,
                     f"Upload: {stem}{ext}")
    return job_id


def job_status(job_id: str) -> dict | None:
    if not JOB_RE.fullmatch(job_id or ""):
        return None
    with _jobs_lock:
        j = _jobs.get(job_id)
        return None if j is None else dict(status=j["status"], progress=j["progress"], stage=j["stage"],
                                           bundle=j["bundle"], log=list(j["log"]), error=j["error"])


# ----------------------------------------------------------------------------------------------- attacks
def _load_bundle(d: Path):
    from PIL import Image
    from .imageio import decode_normals
    m = json.loads((d / "manifest.json").read_text())
    rgb = np.asarray(Image.open(d / "image.png").convert("RGB"))
    normals = decode_normals(np.asarray(Image.open(d / "normals.png").convert("RGB")))
    unc = np.asarray(Image.open(d / "unc.png").convert("L"), np.float32) / 255.0 * 45.0
    labels = np.asarray(Image.open(d / "labels.png").convert("L")).astype(np.int32)
    return m, rgb, normals, unc, labels


def _bundle_cfg(m: dict) -> Config:
    c = m.get("calibration", {})
    base = Config()
    tau = float(c.get("tau_img", base.tau_img))
    tau_ref = float(c.get("tau_ref", tau))
    kw = dict(kde_h=float(c.get("h", base.kde_h)), T=float(c.get("T", base.T)), tau_img=tau,
              tau_ref_factor=tau_ref / tau if tau else 1.0, w_min=float(c.get("w_min", base.w_min)),
              alpha=float(c.get("alpha", base.alpha)))
    for k in ("eps", "w_glint", "w_contour", "min_reliable", "broad_consensus_frac"):
        if c.get(k) is not None:
            kw[k] = type(getattr(base, k))(c[k])
    return replace(base, **kw)


def attack_bundle(name: str, region_id: int, variants, sigma_att: float = 0.0, root: Path = BUNDLES) -> list[dict]:
    """Re-runs the audit of a bundle from its files and attacks one region; rewrites the bundle with the attacks.

    The base audit is recomputed with lightaudit.pipeline.audit from the bundle's image, normals.png, unc.png and
    labels.png (8-bit encodings, so its numbers can differ slightly from the original audit), keeping the
    manifest's region names, exclusion flags, pseudo-regions and calibration. Attacker normals = the bundle's
    normals (white-box). Attacks already in the bundle with other variant names are kept (merged) in the manifest;
    a variant with the same name is replaced.
    Returns [{variant, title, verdict, S_img, S_img_before, verdict_before, fidelity, interpretation, region_id}].
    """
    from .attacks import run_attack
    from .bundle import write_bundle
    from .pipeline import audit
    check_bundle_name(name)
    d = Path(root) / name
    if not (d / "manifest.json").is_file():
        raise FileNotFoundError(f"no bundle named {name}")
    variants = [v.strip() for v in (variants.split(",") if isinstance(variants, str) else variants) if v.strip()]
    bad = [v for v in variants if v not in ATTACK_VARIANTS]
    if bad or not variants:
        raise ValueError(f"variants must be among {ATTACK_VARIANTS}")
    sigma_att = float(sigma_att)
    if not 0.0 <= sigma_att <= 90.0:
        raise ValueError("sigma_att must be between 0 and 90 degrees")
    lock = _bundle_locks.setdefault(name, threading.Lock())
    with lock:
        m, rgb, normals, unc, labels = _load_bundle(d)
        cfg = _bundle_cfg(m)
        fov = float(m["image"].get("fov_deg", 60.0))
        regs = [r for r in m["regions"] if r.get("kind", "region") == "region"]
        meta = [dict(id=int(r["id"]), name=r["name"], source=m.get("regions_backend", ""),
                     excluded=bool(r.get("excluded", False)), exclude_reason=r.get("reason") or "excluded")
                for r in regs]
        target = next((r for r in meta if r["id"] == int(region_id)), None)
        if target is None or not (labels == target["id"]).any():
            raise ValueError(f"region {region_id} is not a region of bundle {name}")
        if target["excluded"]:
            raise ValueError(f"region {region_id} is excluded from the audit; attacking it is meaningless")
        pseudo = []
        pr = [r for r in m["regions"] if r.get("kind") == "pseudo"]
        if pr:
            L = np.fromfile(d / "landscapes.bin", "<f4").reshape(len(m["regions"]), -1)
            pseudo = [dict(name=r["name"], A=L[r["landscape_index"]].copy(), weight=r["weight"],
                           cue=(r.get("cues") or ["shadow"])[0]) for r in pr]
        base = audit(rgb, normals, unc, labels, meta, cfg, fov, seed=0, pseudo=pseudo)
        base.update(ground_truth=m.get("ground_truth"), normals_backend=m.get("normals_backend", "unknown"),
                    regions_backend=m.get("regions_backend", "unknown"),
                    backends_log=list(m.get("backends_log", [])) + [
                        f"attack lab: base audit re-run from the bundle files for attacks {variants} on region {region_id}"],
                    calib_source=m.get("calibration", {}).get("source", "calib_default.json"))

        def reaudit(img):
            return audit(img, normals, unc, labels, meta, cfg, fov, seed=0, reuse=base, changed=[target["id"]],
                         pseudo=pseudo)

        attacks = [run_attack(v, base, target["id"], reaudit, normals_att=normals, sigma_att=sigma_att, seed=0, cfg=cfg)
                   for v in variants]
        new_names = {a["variant"] for a in attacks}
        kept = [a for a in m.get("attacks", []) if a.get("variant") not in new_names
                and (d / "attacks" / a.get("variant", "") / "manifest.json").is_file()]
        write_bundle(base, name, m.get("title", name), m.get("description", ""), m["image"].get("source", "synthetic"),
                     attacks=attacks, root=Path(root))
        m2 = json.loads((d / "manifest.json").read_text())
        m2["attacks"] = kept + m2["attacks"]
        if m.get("baseline_ls", {}).get("present") and (d / "landscapes_ls.bin").is_file():
            m2["baseline_ls"] = m["baseline_ls"]  # same regions; the LS baseline of the original audit stays valid
        (d / "manifest.json").write_text(json.dumps(m2, indent=1))
    fb = base["fusion"]
    return [dict(variant=a["variant"], title=a["title"], verdict=a["result"]["fusion"]["verdict"],
                 S_img=float(a["result"]["fusion"]["S_img"]) if a["result"]["fusion"]["S_img"] is not None else None,
                 verdict_before=fb["verdict"], S_img_before=float(fb["S_img"]) if fb["S_img"] is not None else None,
                 fidelity=a["fidelity"], interpretation=a["interpretation"], region_id=a["region_id"])
            for a in attacks]


# ----------------------------------------------------------------------------------------------- app
def create_app() -> FastAPI:
    from . import __version__, backends_available

    app = FastAPI(title="LightAudit", version=__version__,
                  description="Lighting-consistency audit. A flag means 'send for human review', never 'fraud'.")

    @app.middleware("http")
    async def revalidate(request, call_next):
        # viewer code and bundles change when the project is rebuilt: make browsers revalidate instead of reusing
        # a heuristically cached copy (a stale viewer showed an old verdict for a rebuilt bundle)
        resp = await call_next(request)
        if request.url.path.startswith(("/viewer", "/bundles", "/data", "/results")):
            resp.headers["Cache-Control"] = "no-cache"
        return resp

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/viewer/index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__, "backends": backends_available(), "server": "fastapi"}

    @app.post("/api/audit")
    async def api_audit(image: UploadFile = File(...), roi: UploadFile | None = File(None),
                        normals: str = Form("dsine,stablenormal"), regions: str = Form("sam"), fov: float = Form(60.0)):
        data = await image.read(MAX_UPLOAD + 1)
        roi_data = await roi.read(MAX_UPLOAD + 1) if roi is not None and roi.filename else None
        try:
            job_id = submit_audit(data, image.filename, roi_data, normals, regions, fov)
        except OverflowError as e:
            raise HTTPException(413, str(e))
        except Exception as e:
            raise HTTPException(400, f"{type(e).__name__}: {e}")
        return {"job_id": job_id}

    @app.get("/api/jobs/{job_id}")
    def api_job(job_id: str):
        j = job_status(job_id)
        if j is None:
            raise HTTPException(404, "unknown job")
        return j

    @app.post("/api/attack")
    def api_attack(payload: dict = Body(...)):
        try:
            name = check_bundle_name(str(payload.get("bundle", "")))
            region = int(payload["region"])
            variants = payload.get("variants", list(ATTACK_VARIANTS))
            sigma = float(payload.get("sigma_att", 0.0))
        except (KeyError, TypeError, ValueError) as e:
            raise HTTPException(400, f"bad request: {e}")
        try:
            results = attack_bundle(name, region, variants, sigma)
        except FileNotFoundError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))
        return {"bundle": name, "results": results}

    for prefix, folder in STATIC.items():  # read-only: StaticFiles only answers GET/HEAD and blocks traversal
        app.mount(prefix, StaticFiles(directory=str(folder), check_dir=False), name=prefix.strip("/").replace("/", "_"))
    return app


app = create_app()


def serve(port: int = 8000, host: str = "127.0.0.1") -> None:
    import uvicorn
    for folder in STATIC.values():
        folder.mkdir(parents=True, exist_ok=True)
    print(f"LightAudit viewer: http://{host}:{port}/  (Ctrl+C to stop)")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    serve()
