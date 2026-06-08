# Redrob Winning Candidate Ranker

**Author:** Participant (User)
Competition-grade CPU-only ranking system for the Redrob Intelligent Candidate Discovery & Ranking Challenge.

It ranks 100,000 candidate profiles for the **Senior AI Engineer, Founding Team** JD and produces the required top-100 CSV.

```bash
python rank.py --candidates ./candidates.jsonl --out ./submission.csv --debug ./top_debug.jsonl
python validate_submission.py ./submission.csv
```

The final ranking step is:

- CPU only
- no GPU
- no network
- no hosted LLM calls
- deterministic
- tested on the provided 100K candidate file

In this environment the full run completed in about **22 seconds** with less than **400 MB RAM**.

## Why this approach is stronger than keyword matching

The JD is deliberately written to punish shallow AI keyword matching. The system therefore ranks candidates by recruiter-style evidence:

1. Did they ship production retrieval, search, ranking, recommendation, or candidate matching systems?
2. Do they understand evaluation: NDCG, MRR, MAP, A/B testing, offline-to-online correlation?
3. Are they a senior hands-on engineer in the approximate 5–9 year band?
4. Do they have product-company exposure rather than pure services or pure research?
5. Are the Redrob behavioral signals hireable: active recently, open to work, responsive, low notice period?
6. Is the profile internally consistent, or does it look like a honeypot / keyword-stuffed profile?
7. Is the candidate logistically realistic for Pune/Noida hybrid expectations?

## Architecture

```text
candidates.jsonl
   |
   v
Stage 1: ultra-fast high-recall prefilter over all 100K
   - current title fit
   - experience band fit
   - core skill evidence
   - product/service career approximation
   - Redrob availability signals
   - location/logistics
   - cheap honeypot indicators
   |
   v
Top shortlist, default 3,000
   |
   v
Stage 2: expensive recruiter-style reading
   - career text evidence scanner
   - semantic JD-facet scorer
   - production retrieval/ranking evidence
   - evaluation framework evidence
   - recommendation / marketplace matching evidence
   - career trajectory and product-company fit
   - robust honeypot/profile-integrity penalties
   |
   v
Stage 3: rank fusion
   - deterministic teacher-rubric score
   - rule score
   - evidence score
   - semantic facet score
   - career score
   - behavioral score
   |
   v
submission.csv
```

## Files

```text
rank.py                       single-command final ranking script
src/config.py                 JD-specific constants, facets, regex groups
src/features.py               feature engineering, honeypot detection, teacher-rubric proxy
src/fusion.py                 reciprocal-rank fusion over ranking views
src/reasoning.py              grounded per-candidate reasoning generator
src/io.py                     JSONL reader
src/text_utils.py             text normalization helpers
src/utils.py                  small utility functions
validate_submission.py        official validator copied from challenge bundle
submission.csv                generated top-100 submission
submission_metadata.yaml      portal metadata template to edit before upload
app.py                        small Streamlit sandbox demo for sample files
requirements.txt              minimal runtime dependencies
requirements-demo.txt         Streamlit sandbox dependencies
scripts/audit_submission.py   quick audit of generated debug output
scripts/create_teacher_prompts.py optional LLM-teacher prompt generator for offline iteration
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`orjson` is recommended for speed but the code has a standard-library fallback.

## Run full ranking

Put `candidates.jsonl` in the repo root or pass the absolute path:

```bash
python rank.py --candidates ./candidates.jsonl --out ./submission.csv --debug ./top_debug.jsonl
```

Optional speed/recall control:

```bash
python rank.py --candidates ./candidates.jsonl --out ./submission.csv --shortlist-n 5000
```

The default `--shortlist-n 3000` is the best speed-quality tradeoff I used for the packaged output.

Validate:

```bash
python validate_submission.py ./submission.csv
```

Expected:

```text
Submission is valid.
```

## Ranking method in plain English

The system treats the JD as several recruiter facets, not a bag of keywords:

- production retrieval and semantic/vector search
- ranking and relevance evaluation
- product ML / recommendation systems
- recruiter or candidate matching workflows
- senior hands-on shipper behavior
- LLM/RAG depth as a bonus, not the main signal

A candidate with many AI skills but no production evidence is capped. A candidate with strong production recommendation/search history can rank well even when their profile does not say every buzzword.

## Honeypot protection

The ranker penalizes:

- nontechnical titles stuffed with AI skills
- many expert skills with near-zero duration
- profile years that contradict summary/career history
- services-only trajectories
- pure research without production deployment
- framework-only LangChain/prompt profiles
- CV/speech/robotics-heavy profiles without NLP/IR evidence
- title-hopping with short tenures
- outside-India logistics when relocation is not realistic

## Reasoning generation

The `reasoning` column is generated from real candidate fields only:

- current title
- years of experience
- company and location
- matched listed skills
- career evidence categories
- response rate, last active date, notice period
- honest concerns such as notice period, inactive status, outside India, or consistency risk

No reasoning string mentions a skill or employer unless it exists in that candidate profile.

## Optional AI-teacher iteration

The final `rank.py` does **not** call any hosted AI model. However, the repo includes `scripts/create_teacher_prompts.py` so you can generate review prompts for GPT/Claude/Gemini during development. Use that only offline during iteration, then encode improvements back into deterministic rules or artifacts. Do not call APIs inside `rank.py`.

Example:

```bash
python scripts/create_teacher_prompts.py --debug top_debug.jsonl --out teacher_prompts.jsonl --n 200
```

## Sandbox demo

For Streamlit Cloud / HuggingFace Spaces:

```bash
pip install -r requirements-demo.txt
streamlit run app.py
```

The demo accepts a small JSONL sample and produces a ranked CSV. It is meant for the challenge sandbox requirement, not for running the full 100K pool in a browser.

### App Preview

![Streamlit Sandbox Demo Initial State](C:/Users/USER/.gemini/antigravity-ide/brain/cdc07baf-1796-4b8e-baaa-faa189a4927e/initial_state_1780911322410.png)

### Working Walkthrough

![Streamlit Sandbox Demo Recording](C:/Users/USER/.gemini/antigravity-ide/brain/cdc07baf-1796-4b8e-baaa-faa189a4927e/streamlit_demo_1780911298862.webp)

## Methodology summary for portal

A two-stage hybrid recruiter-style ranker. Stage 1 performs an ultra-fast high-recall scan over all 100K profiles using title, seniority, core retrieval/ranking skills, career trajectory, location, availability, and cheap honeypot checks. Stage 2 deeply scores the shortlist using career-text evidence for shipped production retrieval, semantic/vector search, ranking evaluation, recommendation systems, product-company work, and LLM/RAG depth. Final ordering uses deterministic teacher-rubric scoring plus reciprocal-rank fusion across rule, semantic, evidence, career, and behavioral views. The system aggressively penalizes keyword stuffing, impossible skill claims, pure research, services-only backgrounds, wrong-domain CV/speech profiles, and unavailable candidates. Reasoning is generated only from profile-grounded facts.
