"""Loader for the shared company-alias registry (data/company_aliases.json)."""

from __future__ import annotations

import json
from pathlib import Path

ALIAS_PATH = Path(__file__).resolve().parent.parent / "data" / "company_aliases.json"


def load(path: Path | str = ALIAS_PATH) -> dict[str, dict]:
    p = Path(path)
    if not p.exists():
        return {}
    return {k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items()
            if not k.startswith("_")}


def variants_for(company_id: str, registry: dict | None = None) -> list[str]:
    reg = registry if registry is not None else load()
    return list(reg.get(company_id, {}).get("name_variants", []))
