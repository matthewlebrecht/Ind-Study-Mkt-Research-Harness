#!/usr/bin/env python3
"""
Build the H-FIRSTPARTY-01 page fixtures: the cached page behind every FIRSTPARTY observation (convention 40 -- the
extraction fix is verified against the pages its rows came from, not against pages chosen to pass).

The harness cache lives under harness_output/, which git ignores, so a test that read it would pass here and fail on a
fresh clone -- the failure the audit artifacts had before 2026-09-01. Each fixture is the cached page with its
<script>/<style>/<noscript>/<svg>/<template> elements and comments removed -- exactly the first step of
harnesses/h_firstparty_01/body.py::extract, so the extractor's input is identical -- gzipped. index.json records, per
source URL, the cache partition it came from, the SHA-256 of the cached file and of the fixture text, and the rows it
serves; URLs with no cached page are listed, not skipped silently.

    python core/tests/fixtures/firstparty_pages/build_fixtures.py
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))

import openpyxl  # noqa: E402

from core.cache import slug  # noqa: E402
from harnesses.h_execid_01.source import _unwrap  # noqa: E402
from harnesses.h_firstparty_01.body import _NON_TEXT  # noqa: E402

RAW = ROOT / "harness_output" / "H-FIRSTPARTY-01" / "raw" / "pages"


def cache_file(url: str) -> Path | None:
    key = "p_" + slug(url.replace("https://", "").replace("http://", ""), maxlen=110) + ".txt"
    parts = sorted((p for p in RAW.iterdir() if p.is_dir() and (p / key).exists()), reverse=True)
    return parts[0] / key if parts else None


def main() -> int:
    wb = openpyxl.load_workbook(ROOT / "data" / "market_intel_db.xlsx", read_only=True, data_only=True)
    it = wb["Observations"].iter_rows(values_only=True)
    h = list(next(it))
    urls: dict[str, list[str]] = {}
    for r in it:
        if r and r[0] and r[h.index("harness_id")] == "H-FIRSTPARTY-01":
            urls.setdefault(str(r[h.index("source_url")]), []).append(str(r[0]))
    index, missing, total = {}, {}, 0
    for n, (url, ids) in enumerate(sorted(urls.items()), 1):
        src = cache_file(url)
        if src is None:
            missing[url] = sorted(ids)
            continue
        raw = src.read_bytes()
        status, html = _unwrap(raw.decode("utf-8"))
        text = _NON_TEXT.sub(" ", html)
        name = f"page_{n:03d}.html.gz"
        data = gzip.compress(text.encode("utf-8"), compresslevel=9, mtime=0)
        (HERE / name).write_bytes(data)
        total += len(data)
        index[url] = {"file": name, "status": status, "cache_partition": src.parent.name, "cache_file": src.name,
                      "cache_sha256": hashlib.sha256(raw).hexdigest(),
                      "fixture_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "observation_ids": sorted(ids)}
    (HERE / "index.json").write_text(json.dumps({
        "built_from": "every H-FIRSTPARTY-01 observation's source_url in data/market_intel_db.xlsx, cached page under "
                      "harness_output/H-FIRSTPARTY-01/raw/pages (latest partition holding it)",
        "transformation": "status line unwrapped; <script>/<style>/<noscript>/<svg>/<template> and comments removed "
                          "(body.py::_NON_TEXT, the extractor's own first step); gzip",
        "pages": index, "urls_without_a_cached_page": missing}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{len(index)} fixtures, {total:,} bytes gzipped; {len(missing)} URL(s) without a cached page: {sorted(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
