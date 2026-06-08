#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug", default="top_debug.jsonl")
    args = ap.parse_args()
    rows = [json.loads(line) for line in open(args.debug, encoding="utf-8") if line.strip()]
    print(f"Rows: {len(rows)}")
    print("Titles:")
    for k, v in Counter(r.get("title") for r in rows).most_common():
        print(f"  {v:3d}  {k}")
    outside = [r for r in rows if r.get("features", {}).get("outside_india_penalty", 0) > 0]
    issue_rows = [r for r in rows if r.get("issues")]
    print(f"Outside India rows: {len(outside)}")
    print(f"Rows with profile-integrity issues: {len(issue_rows)}")
    print("Top 10:")
    for r in rows[:10]:
        print(f"  {r['rank']:3d} {r['candidate_id']} {r['fused_score']:.4f} {r['title']} | {r['location']} | {r['company']}")

if __name__ == "__main__":
    main()
