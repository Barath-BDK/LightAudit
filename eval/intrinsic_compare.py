"""Matched-false-alarm comparison of learned vs Retinex albedo from saved rows (eval/intrinsic_bench.py wrote them).

    python eval/intrinsic_compare.py [n_boot]     -> data/results/intrinsic_bench.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
from panel_compare import compare  # noqa: E402

n_boot = int(sys.argv[1]) if len(sys.argv) > 1 else 300
rows = json.loads((ROOT / "data" / "results" / "intrinsic_rows.json").read_text())
sets = {"Retinex (T+Tr)": ("T", "Tr"), "learned (T+Tr)": ("Tl", "Trl"), "both (4 tests)": ("T", "Tr", "Tl", "Trl")}
out = {}
for v in ("splice", "harmonised", "feather8", "poisson"):
    sub = [r for r in rows if r["kind"] in ("clean", v)]
    print(f"--- {v} (n clean {sum(r['kind'] == 'clean' for r in sub)}, n paste {sum(r['kind'] == v for r in sub)})", flush=True)
    out[v] = dict(learned=compare(sub, sets, v, "Retinex (T+Tr)", "learned (T+Tr)", n_boot=n_boot),
                  both=compare(sub, sets, v, "Retinex (T+Tr)", "both (4 tests)", n_boot=n_boot, verbose=False))
(ROOT / "data" / "results" / "intrinsic_bench.json").write_text(json.dumps(out, indent=1))
