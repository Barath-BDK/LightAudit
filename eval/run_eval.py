"""Runs the evaluation suite: python -m lightaudit.cli eval --suite quick|full [--exp E1,E4]
(or python eval/run_eval.py quick E1,E4). Resumable: every audit is cached in data/results/cache/."""
from __future__ import annotations

import importlib
import sys
import time
import traceback
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ALL = [f"E{i}" for i in range(1, 11)]


def main(suite: str = "quick", exps: list[str] | None = None) -> dict:
    from eval import common as C
    C.require_calibration()
    exps = [e.strip().upper() for e in (exps or ALL)]
    status = {}
    for e in exps:
        t0 = time.time()
        print(f"== {e} ({suite}) ==", flush=True)
        try:
            mod = importlib.import_module(f"eval.exp_e{int(e[1:])}")
            mod.run(suite)
            status[e] = dict(ok=True, seconds=round(time.time() - t0, 1))
        except Exception as ex:  # keep going: one failing experiment must not kill the rest
            traceback.print_exc()
            status[e] = dict(ok=False, error=f"{type(ex).__name__}: {ex}", seconds=round(time.time() - t0, 1))
        print(f"   {e}: {status[e]}", flush=True)
    prev = C.load_json(f"run_status_{suite}.json") or {}
    prev.update(status)
    C.write_json(f"run_status_{suite}.json", prev)
    return status


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "quick", sys.argv[2].split(",") if len(sys.argv) > 2 else None)
