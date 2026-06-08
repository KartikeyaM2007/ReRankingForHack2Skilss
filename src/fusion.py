from __future__ import annotations
from typing import Dict, List, Tuple
from .features import FeaturePack
from .utils import clamp


def reciprocal_rank_fusion(items: List[Tuple[FeaturePack, object]], score_names: List[Tuple[str, float]], k: int = 60) -> Dict[str, float]:
    """Return per-candidate RRF score over several ranking views."""
    fused = {fp.candidate_id: 0.0 for fp, _ in items}
    for name, weight in score_names:
        def get_score(pair):
            fp = pair[0]
            if name == "final":
                return fp.final_score
            return fp.alt_scores.get(name, fp.features.get(name, 0.0))
        ranked = sorted(items, key=lambda pair: (-get_score(pair), pair[0].candidate_id))
        for r, (fp, _) in enumerate(ranked, 1):
            fused[fp.candidate_id] += weight / (k + r)
    maxv = max(fused.values()) if fused else 1.0
    minv = min(fused.values()) if fused else 0.0
    span = max(1e-12, maxv - minv)
    return {cid: clamp((v - minv) / span) for cid, v in fused.items()}


def final_order(items: List[Tuple[FeaturePack, object]]) -> List[Tuple[float, FeaturePack, object]]:
    views = [
        ("final", 0.36),
        ("teacher", 0.18),
        ("evidence", 0.17),
        ("technical_no_behavior", 0.12),
        ("semantic", 0.09),
        ("career", 0.05),
        ("behavior", 0.03),
    ]
    rrf = reciprocal_rank_fusion(items, views)
    out = []
    for fp, c in items:
        # Final score is the anchor; RRF stabilizes the top-N across views.
        fused = 0.74 * fp.final_score + 0.26 * rrf.get(fp.candidate_id, 0.0)
        # Do not let RRF rescue strong honeypot penalties.
        risk = fp.features.get("integrity_penalty", 0.0) + 0.35 * fp.features.get("text_negative", 0.0)
        fused -= 0.28 * min(1.0, risk)
        out.append((clamp(fused), fp, c))
    return sorted(out, key=lambda x: (-x[0], x[1].candidate_id))
