#!/usr/bin/env python3
"""Optional development helper.

Creates JSONL prompts for offline LLM review of candidates. Do not use this in the final ranking step.
"""
from __future__ import annotations
import argparse, json

RUBRIC = """You are a senior technical recruiter for Redrob AI. Score the candidate for the Senior AI Engineer founding-team JD from 0 to 5.
Prioritize production retrieval/search/ranking/recommendation evidence, evaluation rigor (NDCG/MRR/MAP/A-B), senior hands-on Python ML engineering, product-company background, and hireability signals.
Penalize keyword stuffing, pure research, services-only background, framework-only LangChain/OpenAI demos, CV/speech/robotics without NLP/IR, inconsistency, and poor availability.
Return JSON: {score_0_to_5, risks, strongest_evidence, one_sentence_verdict}.
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug", default="top_debug.jsonl")
    ap.add_argument("--out", default="teacher_prompts.jsonl")
    ap.add_argument("--n", type=int, default=200)
    args = ap.parse_args()
    with open(args.out, "w", encoding="utf-8") as out:
        for i, line in enumerate(open(args.debug, encoding="utf-8")):
            if i >= args.n:
                break
            row = json.loads(line)
            prompt = {
                "candidate_id": row["candidate_id"],
                "prompt": RUBRIC + "\nCandidate debug summary:\n" + json.dumps(row, ensure_ascii=False, indent=2)
            }
            out.write(json.dumps(prompt, ensure_ascii=False) + "\n")
    print(f"Wrote {min(args.n, i+1)} prompts to {args.out}")

if __name__ == "__main__":
    main()
