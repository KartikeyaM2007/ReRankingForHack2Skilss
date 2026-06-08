from __future__ import annotations
import re
from typing import Dict, Any, Iterable, List

_SPACE = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9+#.&/ -]+")


def norm_text(x: str | None) -> str:
    if not x:
        return ""
    x = str(x).lower().replace("–", "-").replace("—", "-")
    x = _NON_ALNUM.sub(" ", x)
    return _SPACE.sub(" ", x).strip()


def build_profile_text(c: Dict[str, Any], include_skills: bool = True) -> str:
    p = c.get("profile", {})
    parts: List[str] = []
    # Repeat high-signal sections lightly. This is our cheap semantic proxy.
    for key in ("current_title", "headline", "summary", "current_industry", "current_company", "location"):
        v = p.get(key)
        if v:
            parts.append(str(v))
            if key in {"current_title", "headline"}:
                parts.append(str(v))
    for h in c.get("career_history", []) or []:
        for key in ("title", "industry", "company", "description"):
            v = h.get(key)
            if v:
                parts.append(str(v))
                if key == "title":
                    parts.append(str(v))
    if include_skills:
        skills = []
        for s in c.get("skills", []) or []:
            name = s.get("name", "")
            if name:
                prof = str(s.get("proficiency", "")).lower()
                repeat = 2 if prof in {"advanced", "expert"} else 1
                skills += [str(name)] * repeat
        parts.extend(skills)
    return norm_text("\n".join(parts))


def build_summary_text(c: Dict[str, Any]) -> str:
    p = c.get("profile", {})
    parts = [p.get("current_title", ""), p.get("headline", ""), p.get("summary", "")]
    parts += [s.get("name", "") for s in c.get("skills", []) or []]
    return norm_text("\n".join(str(x) for x in parts if x))
