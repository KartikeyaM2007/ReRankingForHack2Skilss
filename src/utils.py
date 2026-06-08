from __future__ import annotations
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict
import json

try:
    import orjson  # type: ignore
except Exception:  # pragma: no cover
    orjson = None


def loads_json(line: str) -> Dict[str, Any]:
    if orjson is not None:
        return orjson.loads(line)
    return json.loads(line)


def dumps_json(obj: Any) -> str:
    if orjson is not None:
        return orjson.dumps(obj, option=orjson.OPT_APPEND_NEWLINE).decode("utf-8")
    return json.dumps(obj, ensure_ascii=False) + "\n"


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def safe_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        return int(x)
    except Exception:
        return default


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
