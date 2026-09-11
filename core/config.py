"""
Credential and configuration access, shared by every harness.

Keys live in a `.env` file at the repo root, which is gitignored. `.env.example` is the
committed template listing every key a harness looks for. This module reads that file
itself rather than depending on `python-dotenv`, because the project has no dependency
manifest and every other module here runs on the standard library alone.

Two access functions, and the difference between them matters:

- `get_key` returns `""` for an absent key. Use it where a key is a speed or quality
  optimization and the harness has a working path without it (the FMCSA webkey pattern).
- `require_key` raises `MissingCredential`. Use it where the harness cannot produce
  evidence without the key. A search-backed harness that silently downgrades to "found
  nothing" writes false absence into the evidence base, which convention 6a says is worse
  than a gap because it carries weight. Missing credentials must stop the run and say so.

Real environment variables win over `.env`, so a key exported in a shell or supplied by CI
overrides the file without editing it.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"

_loaded = False


class MissingCredential(RuntimeError):
    """Raised when a harness needs a key that is not configured."""


def _parse(text: str) -> dict[str, str]:
    """Minimal `.env` parse: KEY=value, `#` comments, optional `export `, optional quotes."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def load_env(path: Path | str | None = None, override: bool = False) -> dict[str, str]:
    """Read `.env` into `os.environ`. Idempotent; a missing file is not an error.

    Existing environment variables are preserved unless `override=True`, so an exported
    shell value beats the file.
    """
    global _loaded
    env_path = Path(path) if path is not None else ENV_PATH
    if not env_path.exists():
        _loaded = True
        return {}
    values = _parse(env_path.read_text(encoding="utf-8"))
    for key, value in values.items():
        if override or not os.environ.get(key):
            os.environ[key] = value
    _loaded = True
    return values


def _ensure_loaded() -> None:
    if not _loaded:
        load_env()


def get_key(name: str, default: str = "") -> str:
    """Return a configured value, or `default` if it is absent or blank."""
    _ensure_loaded()
    return os.environ.get(name, "").strip() or default


def require_key(name: str, purpose: str = "") -> str:
    """Return a configured value, or raise `MissingCredential` naming how to fix it."""
    value = get_key(name)
    if value:
        return value
    detail = f" {purpose}" if purpose else ""
    raise MissingCredential(
        f"{name} is not configured.{detail} "
        f"Add a line `{name}=...` to {ENV_PATH} (copy {REPO_ROOT / '.env.example'} if it "
        f"does not exist yet), or export it in the environment. "
        f"The run is stopping rather than recording an absence it cannot distinguish "
        f"from a missing credential."
    )


def configured_keys(names: list[str]) -> dict[str, bool]:
    """Presence map for a list of key names. For preflight reporting, never logs values."""
    _ensure_loaded()
    return {name: bool(get_key(name)) for name in names}
