#!/usr/bin/env python3
"""
Redrob Intelligent Candidate Discovery ranker.

Single-command reproduction:
    python rank.py --candidates ./candidates.jsonl --out ./submission.csv --debug ./top_debug.jsonl

The ranking step is CPU-only, network-free, and uses no hosted LLM calls.
"""
from __future__ import annotations
import argparse
import csv
import heapq
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Allow running from repo root without installing as a package.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.features import fast_prefilter_score, final_features, FeaturePack  # noqa: E402
from src.fusion import final_order  # noqa: E402
from src.reasoning import make_reason  # noqa: E402
from src.io import iter_candidates  # noqa: E402
from src.utils import dumps_json, ensure_parent  # noqa: E402


def _heap_push_top(heap: list, key: tuple, item: tuple, limit: int) -> None:
    wrapped = (key, item)
    if len(heap) < limit:
        heapq.heappush(heap, wrapped)
    elif key > heap[0][0]:
        heapq.heapreplace(heap, wrapped)


def build_shortlist(candidates_path: Path, shortlist_n: int) -> List[Dict[str, Any]]:
    """Cheap high-recall scan over the full 100K file."""
    heap: List[Tuple[tuple, tuple]] = []
    # A small reserve for rare high-signal titles, so cheap score cannot accidentally miss them.
    rare_title_heap: List[Tuple[tuple, tuple]] = []
    for c in iter_candidates(candidates_path):
        cheap_score, cheap_meta = fast_prefilter_score(c)
        cid = c.get("candidate_id", "")
        try:
            cid_num = int(str(cid).split("_")[-1])
        except Exception:
            cid_num = 0
        key = (float(cheap_score), -cid_num)
        _heap_push_top(heap, key, (c, cheap_meta), shortlist_n)
        title_key_score = cheap_meta.get("title_score", 0.0) + 0.30 * cheap_meta.get("career_score", 0.0) + 0.20 * cheap_meta.get("skill_fit", 0.0)
        if cheap_meta.get("title_score", 0.0) >= 0.72:
            _heap_push_top(rare_title_heap, (title_key_score, -cid_num), (c, cheap_meta), max(1000, shortlist_n // 5))
    selected: Dict[str, Dict[str, Any]] = {}
    for _, (c, _) in heap + rare_title_heap:
        selected[c["candidate_id"]] = c
    return list(selected.values())


def rank_candidates(candidates_path: Path, out_path: Path, debug_path: Path | None = None, top_n: int = 100, shortlist_n: int = 9000) -> List[Tuple[float, FeaturePack, Dict[str, Any]]]:
    shortlist = build_shortlist(candidates_path, shortlist_n=shortlist_n)
    scored: List[Tuple[FeaturePack, Dict[str, Any]]] = []
    for c in shortlist:
        fp = final_features(c)
        scored.append((fp, c))
    ordered = final_order(scored)
    top = ordered[:top_n]

    ensure_parent(out_path)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["candidate_id", "rank", "score", "reasoning"])
        prev_score = None
        for rank, (score, fp, c) in enumerate(top, 1):
            # Monotone score, deterministic tie behavior.
            out_score = round(float(score), 6)
            if prev_score is not None and out_score > prev_score:
                out_score = prev_score
            prev_score = out_score
            w.writerow([fp.candidate_id, rank, f"{out_score:.6f}", make_reason(c, fp, rank)])

    if debug_path:
        ensure_parent(debug_path)
        with open(debug_path, "w", encoding="utf-8") as f:
            for rank, (score, fp, c) in enumerate(top, 1):
                p = c.get("profile", {})
                row = {
                    "rank": rank,
                    "fused_score": score,
                    "candidate_id": fp.candidate_id,
                    "title": p.get("current_title"),
                    "years": p.get("years_of_experience"),
                    "location": p.get("location"),
                    "company": p.get("current_company"),
                    "industry": p.get("current_industry"),
                    "alt_scores": fp.alt_scores,
                    "features": {k: fp.features[k] for k in sorted(fp.features) if k not in {"profile_text", "summary_text"}},
                    "issues": fp.meta.get("issues", []),
                    "matched_skills": fp.meta.get("matched_skills", []),
                    "reasoning": make_reason(c, fp, rank),
                }
                f.write(dumps_json(row))
    return top


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument("--debug", default=None, help="Optional debug JSONL for the top candidates")
    ap.add_argument("--top-n", type=int, default=100)
    ap.add_argument("--shortlist-n", type=int, default=9000, help="Cheap-stage shortlist size; increase for maximum recall")
    args = ap.parse_args()
    rank_candidates(
        Path(args.candidates),
        Path(args.out),
        Path(args.debug) if args.debug else None,
        top_n=args.top_n,
        shortlist_n=args.shortlist_n,
    )


if __name__ == "__main__":
    main()
