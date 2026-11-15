"""Rule-based explanation sentences, generated only from the numbers (BUILD_SPEC 7.14). Mirrored in viewer/text.js."""
from __future__ import annotations

from collections import Counter

import numpy as np

CUE_NAMES = {"shading": "shading", "glint": "specular highlight", "contour": "silhouette", "shadow": "shadow pairs", "panel": "panel comparison"}
REVIEW = "A flag means \"send for human review\", never \"this is fraud\"."


def explain(fusion: dict, regions: list[dict], eps: float = 1e-3) -> str:
    """regions[i] must carry name, cues, reason; order = fusion['per_region'] order."""
    v, per = fusion["verdict"], fusion["per_region"]
    rel = [p for p in per if p["reliable"]]
    if v == "CONSISTENT":
        c = fusion["consensus"]
        top = per[fusion["top_region"]]
        return (f"{len(rel)} regions agree on one light direction (about {c['az_deg']:.0f}° azimuth, "
                f"{c['el_deg']:.0f}° elevation). The largest disagreement is {regions[top['index']]['name']} at "
                f"{top['angle_deg']:.0f}° (below the alert level).")
    if v == "SUSPICIOUS":
        out = []
        for k in fusion["flagged"]:
            p, r = per[k], regions[k]
            if k in fusion.get("panel_flagged", []):
                out.append(f"The brightness of **{r['name']}** is not predicted by the shading of the panel around it "
                           f"(shared-material score {p['panel_z']:.1f} times the alert level): it looks lit "
                           "differently from its surroundings.")
                continue
            agree = float(np.exp(-p["shortfall"])) - eps
            cues = ", ".join(CUE_NAMES.get(c, c) for c in r["cues"])
            out.append(f"The estimate for **{r['name']}** points {p['angle_deg']:.0f}° away from where "
                       f"{len(rel) - len(fusion['flagged'])} other regions agree. Its own light map does not overlap "
                       f"the consensus (agreement {max(agree, 0):.2f}; shortfall {p['shortfall']:.1f} > alert "
                       f"{fusion['tau']:.1f}). Cues: {cues}.")
        return " ".join(out) + " Please review manually. " + REVIEW
    if v == "INSUFFICIENT":
        counts = Counter(r["reason"] for p, r in zip(per, regions) if not p["reliable"] and not p["excluded"] and r.get("reason"))
        why = "; ".join(f"{n} region(s): {k}" for k, n in counts.most_common()) or fusion["reason"]
        if counts and fusion["reason"]:
            why = f"{fusion['reason']} ({why})"
        return (f"Not enough usable lighting evidence: {why}. "
                "Try a photo outdoors in direct light with several objects visible.")
    return ("The reference regions disagree among themselves, which usually means several lights or unreliable "
            "geometry. No automatic decision.")
