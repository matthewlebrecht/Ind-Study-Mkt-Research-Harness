"""
Date-partitioned response cache, shared by every harness.

Sources drift. FMCSA republishes its snapshot every few days; job boards change hourly.
An observation written last week can only be defended if the exact bytes it was derived
from are still on disk, so the cache is an evidence archive first and a speed optimization
second.

Layout:

    harness_output/<harness_id>/raw/<retrieval-date>/<key><suffix>

Partitioning by date means a re-run *adds* a partition instead of overwriting the evidence
behind rows an earlier run already wrote. Live runs always fetch, because today's partition
starts empty. `offline=True` replays the most recent partition holding each response.
"""

from __future__ import annotations

import datetime as _dt
import re
import time
from pathlib import Path


def slug(text: str, maxlen: int = 80) -> str:
    """Filesystem-safe cache key fragment."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(text))[:maxlen].strip("_")


class DatedCache:
    def __init__(self, root: Path | str, offline: bool = False,
                 retrieval_date: str | None = None, pause_seconds: float = 1.0):
        self.root = Path(root)
        self.retrieval_date = retrieval_date or _dt.date.today().isoformat()
        self.partition = self.root / self.retrieval_date
        self.partition.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self.pause_seconds = pause_seconds
        self.replayed_from: dict[str, str] = {}
        self.fetch_count = 0

    def _archived(self, filename: str) -> Path | None:
        """Most recent dated partition holding this response, today's included."""
        partitions = sorted((p for p in self.root.iterdir()
                             if p.is_dir() and (p / filename).exists()), reverse=True)
        return partitions[0] / filename if partitions else None

    def get(self, key: str, suffix: str, fetch) -> tuple[str, bool]:
        """Return (body, from_cache). `fetch` is only called on a live miss."""
        filename = f"{key}{suffix}"
        path = self.partition / filename
        if path.exists():
            return path.read_text(encoding="utf-8"), True
        if self.offline:
            archived = self._archived(filename)
            if archived is None:
                raise RuntimeError(f"offline mode and no archived response for {key}")
            self.replayed_from[key] = archived.parent.name
            return archived.read_text(encoding="utf-8"), True
        body = fetch()
        self.fetch_count += 1
        path.write_text(body, encoding="utf-8")
        if self.pause_seconds:
            time.sleep(self.pause_seconds)  # be polite to the origin
        return body, False
