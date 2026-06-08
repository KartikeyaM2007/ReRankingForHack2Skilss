from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple
import math
import re

from .config import (
    TODAY, TARGET_LOCATIONS_STRONG, TARGET_LOCATIONS_GOOD, INDIA_CITY_SIGNALS,
    SERVICE_COMPANIES, SERVICE_INDUSTRIES, PRODUCT_INDUSTRIES, PRODUCT_COMPANIES,
    TOP_TECH_COMPANIES, TITLE_WEIGHTS, NON_TECH_TITLES,
    CORE_SKILLS, VECTOR_DB_SKILLS, RETRIEVAL_SKILLS, RANKING_SKILLS, FRAMEWORK_ONLY_SKILLS,
    NEGATIVE_DOMAIN_SKILLS, COMPILED_EVIDENCE, COMPILED_NEGATIVE, JD_FACETS
)
from .utils import clamp, parse_date, safe_float, safe_int
from .text_utils import norm_text, build_profile_text, build_summary_text


@dataclass
class FeaturePack:
    candidate_id: str
    cheap_score: float
    final_score: float = 0.0
    alt_scores: Dict[str, float] = field(default_factory=dict)
    features: Dict[str, float] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)


EXP_RE = re.compile(r"(\d{1,2}(?:\.\d+)?)\+?\s*(?:years|yrs)\b", re.I)


def prof_multiplier(p: str) -> float:
    return {"beginner": 0.22, "intermediate": 0.52, "advanced": 0.84, "expert": 1.0}.get(str(p).lower(), 0.4)


def title_score(title: str) -> float:
    t = norm_text(title)
    if t in TITLE_WEIGHTS:
        return TITLE_WEIGHTS[t]
    best = 0.0
    for key, val in TITLE_WEIGHTS.items():
        if key in t or t in key:
            best = max(best, val * 0.88)
    # Textual fallback so unusual but relevant titles don't vanish.
    if any(k in t for k in ("search", "retrieval", "ranking", "recommendation")) and any(k in t for k in ("engineer", "scientist")):
        best = max(best, 0.82)
    if "machine learning" in t or " ml " in f" {t} ":
        best = max(best, 0.70)
    if "ai" in t and "engineer" in t:
        best = max(best, 0.78)
    return clamp(best)


def experience_score(years: float) -> float:
    y = float(years)
    if 6.0 <= y <= 8.2:
        return 1.0
    if 5.0 <= y < 6.0 or 8.2 < y <= 9.0:
        return 0.90
    if 4.2 <= y < 5.0 or 9.0 < y <= 10.2:
        return 0.58
    if 3.5 <= y < 4.2 or 10.2 < y <= 11.5:
        return 0.28
    if 11.5 < y <= 13.0:
        return 0.12
    return 0.0


def location_score(c: Dict[str, Any]) -> float:
    p = c.get("profile", {})
    loc = norm_text(p.get("location", ""))
    country = norm_text(p.get("country", ""))
    sig = c.get("redrob_signals", {})
    willing = bool(sig.get("willing_to_relocate"))
    mode = norm_text(sig.get("preferred_work_mode", ""))
    if any(city in loc for city in TARGET_LOCATIONS_STRONG):
        base = 1.0
    elif any(city in loc for city in TARGET_LOCATIONS_GOOD):
        base = 0.91
    elif country == "india" or any(city in loc for city in INDIA_CITY_SIGNALS):
        base = 0.68
    else:
        base = 0.18
    if willing and base < 0.95:
        base += 0.16
    if mode in {"hybrid", "flexible"}:
        base += 0.04
    elif mode == "remote" and base < 0.95:
        base -= 0.03
    return clamp(base)


def skill_score(c: Dict[str, Any]) -> Tuple[float, Dict[str, float], List[str]]:
    total = 0.0
    core_count = vector_count = retrieval_count = ranking_count = framework_count = neg_count = 0
    zero_expert = 0
    matched: List[Tuple[float, str]] = []
    assessment_bonus = 0.0
    assessments = {norm_text(k): safe_float(v) for k, v in (c.get("redrob_signals", {}).get("skill_assessment_scores") or {}).items()}
    for s in c.get("skills", []) or []:
        name_raw = str(s.get("name", ""))
        name = norm_text(name_raw)
        prof = str(s.get("proficiency", "")).lower()
        mult = prof_multiplier(prof)
        dur = safe_float(s.get("duration_months"), 0.0)
        dur_mult = clamp(math.sqrt(max(dur, 0.0) / 48.0), 0.22, 1.18)
        endorsements = safe_float(s.get("endorsements"), 0.0)
        endorse_mult = 1.0 + min(0.10, endorsements / 800.0)
        if name in CORE_SKILLS:
            w = CORE_SKILLS[name]
            val = w * mult * dur_mult * endorse_mult
            if name in assessments:
                assessment_bonus += (assessments[name] / 100.0) * min(1.2, w / 7.5)
            total += val
            core_count += 1
            if prof in {"advanced", "expert"}:
                matched.append((val, name_raw))
        if name in VECTOR_DB_SKILLS and prof in {"advanced", "expert"}:
            vector_count += 1
        if name in RETRIEVAL_SKILLS and prof in {"advanced", "expert"}:
            retrieval_count += 1
        if name in RANKING_SKILLS and prof in {"advanced", "expert"}:
            ranking_count += 1
        if name in FRAMEWORK_ONLY_SKILLS and prof in {"advanced", "expert"}:
            framework_count += 1
        if name in NEGATIVE_DOMAIN_SKILLS and prof in {"advanced", "expert"}:
            neg_count += 1
        if prof == "expert" and dur <= 3:
            zero_expert += 1
    matched_names = [n for _, n in sorted(matched, reverse=True)[:10]]
    raw_score = clamp((total + assessment_bonus * 3.5) / 95.0)
    breadth = clamp((0.10 * min(vector_count, 3) + 0.12 * min(retrieval_count, 4) + 0.12 * min(ranking_count, 2)))
    framework_only_penalty = 0.0
    if framework_count >= 2 and retrieval_count <= 1 and ranking_count == 0:
        framework_only_penalty = 0.22
    negative_domain = clamp(neg_count / 7.0)
    feats = {
        "skill_fit": clamp(0.84 * raw_score + breadth - framework_only_penalty),
        "core_skill_count": float(core_count),
        "vector_skill_count": float(vector_count),
        "retrieval_skill_count": float(retrieval_count),
        "ranking_skill_count": float(ranking_count),
        "framework_skill_count": float(framework_count),
        "negative_domain_skill_count": float(neg_count),
        "zero_month_expert_skill_count": float(zero_expert),
        "framework_only_penalty": framework_only_penalty,
        "negative_domain_skill_penalty": negative_domain,
        "assessment_bonus": clamp(assessment_bonus / 5.0),
    }
    return feats["skill_fit"], feats, matched_names


def evidence_group_score(text: str, group: str, cap: float = 6.0) -> float:
    total = 0.0
    for rgx, weight in COMPILED_EVIDENCE.get(group, []):
        n = len(rgx.findall(text))
        total += min(n, 4) * weight
    return clamp(total / cap)


def negative_group_score(text: str, group: str, cap: float = 4.0) -> float:
    total = 0.0
    for rgx, weight in COMPILED_NEGATIVE.get(group, []):
        n = len(rgx.findall(text))
        total += min(n, 6) * weight
    return clamp(total / cap)


def semantic_facet_score(text: str) -> Tuple[float, Dict[str, float]]:
    feats: Dict[str, float] = {}
    score = 0.0
    for name, cfg in JD_FACETS.items():
        terms = cfg["terms"]
        hit = 0.0
        for term in terms:
            t = norm_text(term)
            # exact phrase hit gets more credit than token fragments
            if t and t in text:
                hit += 1.0
            else:
                toks = [x for x in t.split() if len(x) > 2]
                if toks and all(tok in text for tok in toks):
                    hit += 0.65
        val = clamp(hit / max(3.0, min(8.0, len(terms) * 0.75)))
        feats[f"facet_{name}"] = val
        score += float(cfg["weight"]) * val
    feats["semantic_facet_score"] = clamp(score)
    return feats["semantic_facet_score"], feats


def text_evidence_score(text: str) -> Tuple[float, Dict[str, float]]:
    feats = {f"evidence_{g}": evidence_group_score(text, g) for g in COMPILED_EVIDENCE.keys()}
    negs = {f"negative_{g}": negative_group_score(text, g) for g in COMPILED_NEGATIVE.keys()}
    # Weighted to match JD: retrieval + rank/eval + shipped product > generic LLM.
    score = (
        0.16 * feats["evidence_production"] +
        0.23 * feats["evidence_retrieval"] +
        0.24 * feats["evidence_ranking_eval"] +
        0.14 * feats["evidence_recsys_marketplace"] +
        0.08 * feats["evidence_scale"] +
        0.07 * feats["evidence_llm_depth"] +
        0.08 * feats["evidence_shipper"]
    )
    negative = 0.45 * negs["negative_research_only"] + 0.30 * negs["negative_framework_only"] + 0.12 * negs["negative_wrong_domain"] + 0.13 * negs["negative_services_only_text"]
    feats.update(negs)
    feats["text_evidence"] = clamp(score - 0.35 * negative)
    feats["text_negative"] = clamp(negative)
    return feats["text_evidence"], feats


def career_score(c: Dict[str, Any], text: str | None = None) -> Tuple[float, Dict[str, float]]:
    hist = c.get("career_history", []) or []
    if not hist:
        return 0.0, {"career_relevant_month_share": 0.0, "product_role_share": 0.0, "services_only": 0.0, "avg_tenure_months": 0.0}
    total_months = sum(max(0, safe_int(h.get("duration_months"), 0)) for h in hist) or 1
    relevant_months = 0.0
    product_months = 0.0
    services_months = 0.0
    toptech_months = 0.0
    current_relevant = 0.0
    relevant_roles = 0
    product_relevant_roles = 0
    for idx, h in enumerate(hist):
        dur = max(0, safe_int(h.get("duration_months"), 0))
        title = norm_text(h.get("title", ""))
        industry = norm_text(h.get("industry", ""))
        company = norm_text(h.get("company", ""))
        desc = norm_text(h.get("description", ""))
        rel_title = title_score(title)
        # Description evidence per role is strong, because the JD explicitly says to read career history.
        role_text = " ".join([title, industry, company, desc])
        role_evidence, _ = text_evidence_score(role_text)
        role_relevance = clamp(0.45 * rel_title + 0.55 * role_evidence)
        if role_relevance > 0.45:
            relevant_roles += 1
        relevant_months += dur * role_relevance
        if industry in PRODUCT_INDUSTRIES or company in PRODUCT_COMPANIES:
            product_months += dur
            if role_relevance > 0.40:
                product_relevant_roles += 1
        if industry in SERVICE_INDUSTRIES or company in SERVICE_COMPANIES:
            services_months += dur
        if company in TOP_TECH_COMPANIES:
            toptech_months += dur
        if h.get("is_current"):
            current_relevant = max(current_relevant, role_relevance)
    relevant_share = clamp(relevant_months / total_months)
    product_share = clamp(product_months / total_months)
    services_share = clamp(services_months / total_months)
    avg_tenure = total_months / max(1, len(hist))
    tenure_score = 1.0 if avg_tenure >= 24 else 0.72 if avg_tenure >= 18 else 0.45 if avg_tenure >= 12 else 0.20
    title_chaser_penalty = 0.0
    if len(hist) >= 4 and avg_tenure < 20:
        title_chaser_penalty = min(0.22, (20 - avg_tenure) / 80.0 + 0.06)
    services_only = 1.0 if services_share > 0.82 else 0.0
    toptech_only_penalty = 0.0
    if toptech_months / total_months > 0.80 and product_relevant_roles == 0:
        toptech_only_penalty = 0.08
    score = clamp(
        0.40 * relevant_share +
        0.20 * product_share +
        0.18 * clamp(product_relevant_roles / 2.5) +
        0.10 * current_relevant +
        0.08 * tenure_score +
        0.04 * clamp(relevant_roles / 3.0) -
        0.25 * services_only - title_chaser_penalty - toptech_only_penalty
    )
    feats = {
        "career_relevant_month_share": relevant_share,
        "product_month_share": product_share,
        "services_month_share": services_share,
        "services_only": services_only,
        "current_role_relevance": current_relevant,
        "relevant_role_count": float(relevant_roles),
        "product_relevant_role_count": float(product_relevant_roles),
        "avg_tenure_months": avg_tenure,
        "tenure_score": tenure_score,
        "title_chaser_penalty": title_chaser_penalty,
        "toptech_only_penalty": toptech_only_penalty,
        "career_score": score,
    }
    return score, feats


def behavior_score(c: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    s = c.get("redrob_signals", {})
    last = parse_date(s.get("last_active_date"))
    days_inactive = 999.0 if not last else max(0.0, float((TODAY - last).days))
    if days_inactive <= 30:
        recency = 1.0
    elif days_inactive <= 90:
        recency = 1.0 - (days_inactive - 30.0) / 100.0
    else:
        recency = max(0.0, 0.40 - (days_inactive - 90.0) / 225.0)
    response = clamp(safe_float(s.get("recruiter_response_rate")))
    speed_hours = safe_float(s.get("avg_response_time_hours"), 999.0)
    speed = clamp(1.0 - speed_hours / 168.0)
    completeness = clamp(safe_float(s.get("profile_completeness_score")) / 100.0)
    notice = safe_float(s.get("notice_period_days"), 180.0)
    if notice <= 15:
        notice_score = 1.0
    elif notice <= 30:
        notice_score = 0.92
    elif notice <= 60:
        notice_score = 0.66
    elif notice <= 90:
        notice_score = 0.38
    else:
        notice_score = 0.10
    github = safe_float(s.get("github_activity_score"), -1.0)
    github_score = 0.42 if github < 0 else clamp(github / 100.0)
    interview = clamp(safe_float(s.get("interview_completion_rate"), 0.0))
    offer = safe_float(s.get("offer_acceptance_rate"), -1.0)
    offer_score = 0.50 if offer < 0 else clamp(offer)
    saved = clamp(math.log1p(safe_float(s.get("saved_by_recruiters_30d"), 0.0)) / math.log(80.0))
    views = clamp(math.log1p(safe_float(s.get("profile_views_received_30d"), 0.0)) / math.log(500.0))
    apps = clamp(math.log1p(safe_float(s.get("applications_submitted_30d"), 0.0)) / math.log(40.0))
    verified = (1.0 if s.get("verified_email") else 0.0) + (1.0 if s.get("verified_phone") else 0.0) + (1.0 if s.get("linkedin_connected") else 0.0)
    open_score = 1.0 if s.get("open_to_work_flag") else 0.28
    score = clamp(
        0.16 * open_score + 0.15 * recency + 0.15 * response + 0.07 * speed + 0.07 * completeness +
        0.11 * notice_score + 0.08 * github_score + 0.09 * interview + 0.04 * offer_score +
        0.04 * saved + 0.02 * views + 0.01 * apps + 0.01 * (verified / 3.0)
    )
    return score, {
        "behavior_score": score,
        "days_inactive": days_inactive,
        "recency_score": recency,
        "response_score": response,
        "speed_score": speed,
        "notice_score": notice_score,
        "github_score": github_score,
        "saved_score": saved,
        "views_score": views,
        "open_to_work_score": open_score,
    }


def integrity_penalty(c: Dict[str, Any], text: str | None = None) -> Tuple[float, List[str], Dict[str, float]]:
    p = c.get("profile", {})
    years = safe_float(p.get("years_of_experience"), 0.0)
    title = norm_text(p.get("current_title", ""))
    summary = norm_text(p.get("summary", ""))
    hist = c.get("career_history", []) or []
    total_months = sum(max(0, safe_int(h.get("duration_months"), 0)) for h in hist)
    issues: List[str] = []
    penalty = 0.0
    # Years mismatch between profile and summary/career is a common synthetic honeypot.
    m = EXP_RE.search(summary)
    if m:
        stated = safe_float(m.group(1), years)
        if abs(stated - years) >= 3.0 and max(stated, years) >= 5:
            issues.append(f"experience mismatch: profile {years:.1f}y vs summary {stated:.1f}y")
            penalty += 0.36
    career_years = total_months / 12.0
    if career_years > 0 and abs(career_years - years) >= 3.2 and years >= 5:
        issues.append(f"career months mismatch: profile {years:.1f}y vs roles {career_years:.1f}y")
        penalty += 0.28
    # Skill stuffing: many expert claims with no duration is specifically called out.
    expert_short = 0
    expert_total = 0
    ai_core = 0
    neg_adv = 0
    for s in c.get("skills", []) or []:
        name = norm_text(s.get("name", ""))
        prof = str(s.get("proficiency", "")).lower()
        dur = safe_float(s.get("duration_months"), 0.0)
        if prof == "expert":
            expert_total += 1
            if dur <= 3:
                expert_short += 1
        if name in CORE_SKILLS:
            ai_core += 1
        if name in NEGATIVE_DOMAIN_SKILLS and prof in {"advanced", "expert"}:
            neg_adv += 1
    if expert_short >= 5:
        issues.append(f"{expert_short} expert skills with <=3 months duration")
        penalty += 0.46
    elif expert_short >= 3:
        issues.append(f"{expert_short} very short expert skill claims")
        penalty += 0.18
    if expert_total >= 14 and years < 6:
        issues.append("too many expert skills for seniority")
        penalty += 0.16
    if title in NON_TECH_TITLES and ai_core >= 5:
        issues.append("non-technical current title with AI keyword stuffing")
        penalty += 0.62
    if title in NON_TECH_TITLES:
        penalty += 0.30
    if text:
        # If wrong-domain words dominate and retrieval/ranking evidence is absent, penalize hard.
        wrong = negative_group_score(text, "wrong_domain")
        retr = evidence_group_score(text, "retrieval")
        rank = evidence_group_score(text, "ranking_eval")
        if wrong > 0.45 and retr < 0.25 and rank < 0.25:
            issues.append("primary domain appears CV/speech/robotics rather than NLP/IR")
            penalty += 0.18
    feats = {"integrity_penalty": clamp(penalty, 0.0, 1.2), "integrity_issue_count": float(len(issues))}
    return clamp(penalty, 0.0, 1.2), issues, feats


def cheap_features(c: Dict[str, Any]) -> FeaturePack:
    p = c.get("profile", {})
    cid = c.get("candidate_id", "")
    title = title_score(p.get("current_title", ""))
    years = safe_float(p.get("years_of_experience"), 0.0)
    exp = experience_score(years)
    skill, skill_feats, matched = skill_score(c)
    career, career_feats = career_score(c)
    behavior, behavior_feats = behavior_score(c)
    loc = location_score(c)
    summary_text = build_summary_text(c)
    sem, sem_feats = semantic_facet_score(summary_text)
    penalty, issues, integrity_feats = integrity_penalty(c, summary_text)
    # Cheap score favors recall; final scoring will be stricter.
    cheap = (
        0.21 * title + 0.12 * exp + 0.21 * skill + 0.16 * career +
        0.12 * sem + 0.08 * loc + 0.10 * behavior
    )
    cheap = cheap * (0.80 + 0.20 * behavior) - 0.18 * skill_feats.get("negative_domain_skill_penalty", 0.0) - 0.70 * penalty
    feats = {
        "title_score": title, "experience_score": exp, "years": years, "location_score": loc,
        **skill_feats, **career_feats, **behavior_feats, **sem_feats, **integrity_feats
    }
    meta = {"matched_skills": matched, "issues": issues, "summary_text": summary_text}
    return FeaturePack(cid, clamp(cheap, 0.0, 1.0), features=feats, meta=meta)


def final_features(c: Dict[str, Any]) -> FeaturePack:
    fp = cheap_features(c)
    text = build_profile_text(c)
    text_score, text_feats = text_evidence_score(text)
    sem_score, sem_feats = semantic_facet_score(text)
    career_score_val, career_feats = career_score(c, text)
    penalty, issues, integrity_feats = integrity_penalty(c, text)
    # Refresh features.
    fp.features.update(text_feats)
    fp.features.update(sem_feats)
    fp.features.update(career_feats)
    fp.features.update(integrity_feats)
    fp.features["text_evidence"] = text_score
    fp.features["semantic_facet_score"] = sem_score
    fp.meta["issues"] = issues
    fp.meta["profile_text"] = text
    p = c.get("profile", {})
    title = fp.features["title_score"]
    exp = fp.features["experience_score"]
    skill = fp.features["skill_fit"]
    behavior = fp.features["behavior_score"]
    loc = fp.features["location_score"]
    neg_domain = fp.features.get("negative_domain_skill_penalty", 0.0)
    text_negative = fp.features.get("text_negative", 0.0)
    services_only = fp.features.get("services_only", 0.0)
    # Deterministic LLM-teacher proxy: strong cap logic + weighted technical judgment.
    teacher = (
        0.16 * title + 0.10 * exp + 0.14 * skill + 0.20 * text_score + 0.16 * sem_score +
        0.15 * career_score_val + 0.05 * loc + 0.04 * behavior
    )
    # Disqualifier caps: a great recruiter would not let keywords override these.
    hard_cap = 1.0
    if title < 0.25 and skill < 0.50:
        hard_cap = min(hard_cap, 0.42)
    if fp.features.get("evidence_retrieval", 0.0) < 0.18 and fp.features.get("evidence_ranking_eval", 0.0) < 0.18:
        hard_cap = min(hard_cap, 0.72)
    if text_score < 0.28 and skill < 0.65:
        hard_cap = min(hard_cap, 0.64)
    if services_only > 0.5:
        hard_cap = min(hard_cap, 0.52)
    if penalty >= 0.45:
        hard_cap = min(hard_cap, 0.22)
    if norm_text(p.get("current_title", "")) in NON_TECH_TITLES:
        hard_cap = min(hard_cap, 0.12)
    teacher = min(clamp(teacher), hard_cap)
    rule = (
        0.20 * title + 0.11 * exp + 0.16 * skill + 0.22 * text_score +
        0.16 * career_score_val + 0.07 * loc + 0.08 * behavior
    )
    evidence = clamp(0.34 * text_score + 0.24 * sem_score + 0.22 * career_score_val + 0.12 * skill + 0.08 * title)
    behavioral_adjuster = 0.76 + 0.24 * behavior
    risk_penalty = (
        0.58 * penalty + 0.18 * neg_domain + 0.16 * text_negative +
        0.08 * fp.features.get("title_chaser_penalty", 0.0) +
        0.07 * fp.features.get("framework_only_penalty", 0.0)
    )
    base = 0.37 * teacher + 0.27 * rule + 0.22 * evidence + 0.08 * sem_score + 0.06 * behavior
    final = clamp(base * behavioral_adjuster - risk_penalty)
    # Tiny deterministic tie nudges, never enough to change material model decisions.
    cid_num = safe_int(str(fp.candidate_id).split("_")[-1], 0)
    final += (1.0 - (cid_num % 1000) / 1000.0) * 1e-7
    fp.final_score = clamp(final)
    fp.alt_scores = {
        "teacher": teacher,
        "rule": clamp(rule),
        "evidence": evidence,
        "semantic": sem_score,
        "career": career_score_val,
        "behavior": behavior,
        "technical_no_behavior": clamp(0.24*title + 0.16*exp + 0.20*skill + 0.25*text_score + 0.15*career_score_val),
    }
    return fp

# Fast title/industry-only career approximation for first-stage recall.
def cheap_career_score(c: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    hist = c.get("career_history", []) or []
    if not hist:
        return 0.0, {"career_score": 0.0, "product_month_share": 0.0, "services_only": 0.0, "avg_tenure_months": 0.0}
    total_months = sum(max(0, safe_int(h.get("duration_months"), 0)) for h in hist) or 1
    relevant_months = product_months = services_months = 0.0
    relevant_roles = product_relevant_roles = 0
    current_relevant = 0.0
    for h in hist:
        dur = max(0, safe_int(h.get("duration_months"), 0))
        title = norm_text(h.get("title", ""))
        industry = norm_text(h.get("industry", ""))
        company = norm_text(h.get("company", ""))
        rel = title_score(title)
        if any(k in title for k in ("search", "retrieval", "ranking", "recommendation", "nlp", "machine learning", " ai ", "ml")):
            rel = max(rel, 0.55)
        relevant_months += dur * rel
        if rel > 0.42:
            relevant_roles += 1
        if industry in PRODUCT_INDUSTRIES or company in PRODUCT_COMPANIES:
            product_months += dur
            if rel > 0.35:
                product_relevant_roles += 1
        if industry in SERVICE_INDUSTRIES or company in SERVICE_COMPANIES:
            services_months += dur
        if h.get("is_current"):
            current_relevant = max(current_relevant, rel)
    relevant_share = clamp(relevant_months / total_months)
    product_share = clamp(product_months / total_months)
    services_share = clamp(services_months / total_months)
    avg_tenure = total_months / max(1, len(hist))
    services_only = 1.0 if services_share > 0.82 else 0.0
    score = clamp(0.46 * relevant_share + 0.22 * product_share + 0.17 * clamp(product_relevant_roles/2.5) + 0.10 * current_relevant + 0.05 * clamp(avg_tenure/30.0) - 0.24 * services_only)
    return score, {
        "career_relevant_month_share": relevant_share,
        "product_month_share": product_share,
        "services_month_share": services_share,
        "services_only": services_only,
        "current_role_relevance": current_relevant,
        "relevant_role_count": float(relevant_roles),
        "product_relevant_role_count": float(product_relevant_roles),
        "avg_tenure_months": avg_tenure,
        "career_score": score,
    }

# Override cheap_features with the optimized version used by rank.py imports.
def cheap_features(c: Dict[str, Any]) -> FeaturePack:
    p = c.get("profile", {})
    cid = c.get("candidate_id", "")
    title = title_score(p.get("current_title", ""))
    years = safe_float(p.get("years_of_experience"), 0.0)
    exp = experience_score(years)
    skill, skill_feats, matched = skill_score(c)
    career, career_feats = cheap_career_score(c)
    behavior, behavior_feats = behavior_score(c)
    loc = location_score(c)
    summary_text = build_summary_text(c)
    sem, sem_feats = semantic_facet_score(summary_text)
    penalty, issues, integrity_feats = integrity_penalty(c, summary_text)
    cheap = (
        0.21 * title + 0.12 * exp + 0.22 * skill + 0.15 * career +
        0.12 * sem + 0.08 * loc + 0.10 * behavior
    )
    cheap = cheap * (0.80 + 0.20 * behavior) - 0.18 * skill_feats.get("negative_domain_skill_penalty", 0.0) - 0.70 * penalty
    feats = {
        "title_score": title, "experience_score": exp, "years": years, "location_score": loc,
        **skill_feats, **career_feats, **behavior_feats, **sem_feats, **integrity_feats
    }
    meta = {"matched_skills": matched, "issues": issues, "summary_text": summary_text}
    return FeaturePack(cid, clamp(cheap, 0.0, 1.0), features=feats, meta=meta)

# Ultra-fast first-stage scorer. It intentionally skips regex career-text scans; final_features does the expensive reading on the shortlist.
def fast_prefilter_score(c: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    p = c.get("profile", {})
    title_raw = str(p.get("current_title", ""))
    title_l = title_raw.lower().strip()
    title = TITLE_WEIGHTS.get(title_l, 0.0)
    if not title:
        if "search" in title_l or "recommendation" in title_l or "ranking" in title_l:
            title = 0.82
        elif "machine learning" in title_l:
            title = 0.70
        elif "ai" in title_l and "engineer" in title_l:
            title = 0.78
        elif "nlp" in title_l:
            title = 0.66
    years = safe_float(p.get("years_of_experience"), 0.0)
    exp = experience_score(years)
    total = 0.0; core = vector = retrieval = ranking = neg = framework = expert_short = 0; matched=[]
    for s in c.get("skills", []) or []:
        name_raw = str(s.get("name", ""))
        name = name_raw.lower().strip()
        prof = str(s.get("proficiency", "")).lower()
        mult = 1.0 if prof == "expert" else 0.84 if prof == "advanced" else 0.52 if prof == "intermediate" else 0.22
        dur = safe_float(s.get("duration_months"), 0.0)
        dur_mult = 1.0 if dur >= 48 else 0.75 if dur >= 24 else 0.50 if dur >= 12 else 0.25
        w = CORE_SKILLS.get(name)
        if w:
            val = w * mult * dur_mult
            total += val
            core += 1
            if prof in {"advanced", "expert"}:
                matched.append((val, name_raw))
        if name in VECTOR_DB_SKILLS and prof in {"advanced", "expert"}: vector += 1
        if name in RETRIEVAL_SKILLS and prof in {"advanced", "expert"}: retrieval += 1
        if name in RANKING_SKILLS and prof in {"advanced", "expert"}: ranking += 1
        if name in FRAMEWORK_ONLY_SKILLS and prof in {"advanced", "expert"}: framework += 1
        if name in NEGATIVE_DOMAIN_SKILLS and prof in {"advanced", "expert"}: neg += 1
        if prof == "expert" and dur <= 3: expert_short += 1
    skill = clamp(total / 82.0 + 0.04*min(vector,3) + 0.05*min(retrieval,4) + 0.05*min(ranking,2))
    loc_s = str(p.get("location", "")).lower()
    country = str(p.get("country", "")).lower()
    sig = c.get("redrob_signals", {})
    if "pune" in loc_s or "noida" in loc_s: loc = 1.0
    elif any(x in loc_s for x in ("delhi", "gurgaon", "gurugram", "mumbai", "hyderabad", "bangalore", "bengaluru")): loc = 0.91
    elif country == "india": loc = 0.68
    else: loc = 0.18
    if sig.get("willing_to_relocate") and loc < 0.95: loc += 0.12
    # Cheap behavior without datetime parsing.
    last = str(sig.get("last_active_date", ""))
    recency = 1.0 if last >= "2026-05-01" else 0.72 if last >= "2026-03-01" else 0.25
    response = clamp(safe_float(sig.get("recruiter_response_rate")))
    notice = safe_float(sig.get("notice_period_days"), 180)
    notice_s = 1.0 if notice <= 30 else 0.62 if notice <= 60 else 0.30 if notice <= 90 else 0.08
    open_s = 1.0 if sig.get("open_to_work_flag") else 0.28
    github = safe_float(sig.get("github_activity_score"), -1)
    github_s = 0.42 if github < 0 else clamp(github/100.0)
    behavior = clamp(0.24*open_s + 0.22*recency + 0.22*response + 0.16*notice_s + 0.10*github_s + 0.06*clamp(safe_float(sig.get("interview_completion_rate"))))
    # Cheap career/product from titles and industries only.
    hist = c.get("career_history", []) or []
    total_months = 0; prod_months = serv_months = rel_months = 0.0; rel_roles=0
    for h in hist:
        dur = max(0, safe_int(h.get("duration_months"), 0)); total_months += dur
        ht = str(h.get("title", "")).lower().strip(); ind = str(h.get("industry", "")).lower().strip(); comp = str(h.get("company", "")).lower().strip()
        rel = TITLE_WEIGHTS.get(ht, 0.0)
        if not rel and any(k in ht for k in ("search", "recommendation", "ranking", "retrieval", "machine learning", " ai ", "nlp", "ml")): rel = 0.55
        rel_months += dur * rel
        if rel > 0.35: rel_roles += 1
        if ind in PRODUCT_INDUSTRIES or comp in PRODUCT_COMPANIES: prod_months += dur
        if ind in SERVICE_INDUSTRIES or comp in SERVICE_COMPANIES: serv_months += dur
    denom = max(1.0, float(total_months))
    career = clamp(0.50*(rel_months/denom) + 0.28*(prod_months/denom) + 0.14*clamp(rel_roles/3.0) - 0.28*(1.0 if serv_months/denom > 0.82 else 0.0))
    risk = 0.0
    if title_l in NON_TECH_TITLES and core >= 5: risk += 0.60
    if expert_short >= 5: risk += 0.45
    if framework >= 2 and retrieval <= 1 and ranking == 0: risk += 0.18
    if neg >= 5 and retrieval <= 1 and ranking == 0: risk += 0.20
    score = (0.24*title + 0.11*exp + 0.24*skill + 0.16*career + 0.09*loc + 0.16*behavior)
    score = score * (0.82 + 0.18*behavior) - 0.12*clamp(neg/7.0) - 0.70*risk
    meta = {"title_score": title, "skill_fit": skill, "career_score": career, "behavior_score": behavior, "location_score": loc, "risk": risk, "matched_skills": [n for _, n in sorted(matched, reverse=True)[:8]]}
    return clamp(score), meta

# Override location_score with stronger India/Pune-Noida logistics interpretation from the JD.
def location_score(c: Dict[str, Any]) -> float:
    p = c.get("profile", {})
    loc = str(p.get("location", "")).lower()
    country = str(p.get("country", "")).lower().strip()
    sig = c.get("redrob_signals", {})
    willing = bool(sig.get("willing_to_relocate"))
    mode = str(sig.get("preferred_work_mode", "")).lower().strip()
    if "pune" in loc or "noida" in loc:
        base = 1.0
    elif any(city in loc for city in ("delhi", "gurgaon", "gurugram", "mumbai", "hyderabad", "bangalore", "bengaluru")):
        base = 0.91
    elif country == "india" or any(city in loc for city in INDIA_CITY_SIGNALS):
        base = 0.66
    else:
        # JD says outside India is case-by-case and no visa sponsorship; don't put these in top-10 unless exceptional.
        base = 0.06 if not willing else 0.30
    if willing and country == "india" and base < 0.95:
        base += 0.16
    if mode in {"hybrid", "flexible"} and country == "india":
        base += 0.04
    elif mode == "remote" and country != "india":
        base -= 0.03
    return clamp(base)

# Preserve original final_features then wrap it with logistics-aware cap.
_base_final_features = final_features
def final_features(c: Dict[str, Any]) -> FeaturePack:
    fp = _base_final_features(c)
    p = c.get("profile", {})
    country = str(p.get("country", "")).lower().strip()
    willing = bool(c.get("redrob_signals", {}).get("willing_to_relocate"))
    if country and country != "india":
        cap = 0.70 if willing else 0.60
        fp.final_score = min(fp.final_score, cap)
        fp.alt_scores["teacher"] = min(fp.alt_scores.get("teacher", fp.final_score), cap + 0.02)
        fp.alt_scores["rule"] = min(fp.alt_scores.get("rule", fp.final_score), cap + 0.03)
        fp.alt_scores["technical_no_behavior"] = min(fp.alt_scores.get("technical_no_behavior", fp.final_score), cap + 0.06)
        fp.features["outside_india_penalty"] = 1.0 if not willing else 0.55
    else:
        fp.features["outside_india_penalty"] = 0.0
    return fp
