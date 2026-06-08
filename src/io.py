from __future__ import annotations
from pathlib import Path
from typing import Iterator, Dict, Any
from .utils import loads_json


def iter_candidates(path: Path) -> Iterator[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield loads_json(line)
