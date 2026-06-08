from __future__ import annotations
from typing import Dict, Any, List
from .utils import safe_float
from .text_utils import norm_text


def _fmt_years(x: Any) -> str:
    try:
        y = float(x)
        if abs(y - round(y)) < 0.05:
            return str(int(round(y)))
        return f"{y:.1f}"
    except Exception:
        return str(x)


def _top_skills(c: Dict[str, Any], matched: List[str], max_n: int = 4) -> str:
    skills = matched[:]
    if not skills:
        for s in c.get("skills", []) or []:
            name = s.get("name")
            if name:
                skills.append(str(name))
            if len(skills) >= max_n:
                break
    # Deduplicate preserving order.
    seen = set(); out = []
    for s in skills:
        k = norm_text(s)
        if k and k not in seen:
            seen.add(k); out.append(s)
        if len(out) >= max_n:
            break
    return ", ".join(out) if out else "ML/search skills"


def _evidence_phrase(fp) -> str:
    f = fp.features
    bits = []
    if f.get("evidence_retrieval", 0) >= 0.62:
        bits.append("production retrieval or semantic/vector search evidence")
    elif f.get("evidence_retrieval", 0) >= 0.30:
        bits.append("retrieval/search exposure")
    if f.get("evidence_ranking_eval", 0) >= 0.62:
        bits.append("ranking evaluation such as NDCG/MRR/A-B testing")
    elif f.get("evidence_ranking_eval", 0) >= 0.30:
        bits.append("ranking or relevance work")
    if f.get("evidence_recsys_marketplace", 0) >= 0.55:
        bits.append("marketplace/recommendation style matching work")
    if f.get("evidence_llm_depth", 0) >= 0.45:
        bits.append("LLM/RAG or fine-tuning depth")
    if not bits:
        if f.get("skill_fit", 0) >= 0.65:
            bits.append("strong listed ML/retrieval skills but weaker career-text proof")
        else:
            bits.append("adjacent applied ML background")
    return "; ".join(bits[:3])


def make_reason(c: Dict[str, Any], fp, rank: int | None = None) -> str:
    p = c.get("profile", {})
    s = c.get("redrob_signals", {})
    title = p.get("current_title", "Candidate")
    years = _fmt_years(p.get("years_of_experience", ""))
    loc = p.get("location", "")
    company = p.get("current_company", "")
    skills = _top_skills(c, fp.meta.get("matched_skills", []))
    evidence = _evidence_phrase(fp)
    f = fp.features
    positives = []
    if f.get("career_score", 0) >= 0.70:
        positives.append("career history aligns strongly with the JD")
    elif f.get("career_score", 0) >= 0.45:
        positives.append("career history has relevant applied ML/search overlap")
    if f.get("experience_score", 0) >= 0.88:
        positives.append("fits the preferred seniority band")
    if f.get("product_month_share", 0) >= 0.45:
        positives.append("has product-company exposure")
    if f.get("location_score", 0) >= 0.88:
        positives.append("logistically strong for Pune/Noida hybrid expectations")
    if not positives:
        positives.append("kept for specialized technical evidence despite some fit gaps")

    concerns = []
    notice = s.get("notice_period_days")
    if notice is not None and safe_float(notice) > 60:
        concerns.append(f"notice period is {notice} days")
    if not s.get("open_to_work_flag"):
        concerns.append("not marked open to work")
    if safe_float(s.get("recruiter_response_rate"), 1.0) < 0.45:
        concerns.append(f"response rate is {safe_float(s.get('recruiter_response_rate')):.2f}")
    if f.get("negative_domain_skill_penalty", 0) > 0.55:
        concerns.append("some CV/speech-heavy signals are less aligned")
    if fp.meta.get("issues"):
        concerns.append("profile consistency risk was penalized")
    if p.get("country") and norm_text(p.get("country")) != "india":
        concerns.append("outside India")

    concern_txt = f" Concern: {'; '.join(concerns[:2])}." if concerns else ""
    tone = "Strong fit" if (rank or 101) <= 25 else "Relevant fit" if (rank or 101) <= 70 else "Borderline but relevant fit"
    return (
        f"{tone}: {title} with {years} yrs at {company} in {loc}; {evidence}; "
        f"{', '.join(positives[:2])}. Key listed matches: {skills}. "
        f"Availability signals: response rate {safe_float(s.get('recruiter_response_rate')):.2f}, "
        f"last active {s.get('last_active_date')}, notice {s.get('notice_period_days')} days.{concern_txt}"
    )
