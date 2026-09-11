"""
robots.txt compliance gate.

WHY THIS EXISTS, AND WHY IT EXISTS NOW
--------------------------------------
H-EMPREVIEW-01 is the first harness in this project whose named sources actively forbid
automated collection, so it is the first that cannot be written correctly without checking.
The check is not a formality here: it changed what the harness is allowed to read, and
therefore what it is allowed to conclude.

Measured 2026-08-31 against the family-4 sources in `docs/source_lists.md`:

    glassdoor.com      ClaudeBot / anthropic-ai group -> Disallow: /      (also 403s)
    indeed.com         ClaudeBot / anthropic-ai group -> Disallow: /cmp/  (the reviews section)
    careerbliss.com    ClaudeBot group                -> Disallow: /
    comparably.com     no AI-agent group; falls back to *, reviews permitted
    kununu.com         explicit ClaudeBot group with no disallow rules

WHICH IDENTITY APPLIES
----------------------
Indeed publishes several groups. `Claude-User` and `Claude-SearchBot` -- the identities for
a single fetch a person asked for -- carry only narrow restrictions. `ClaudeBot` and
`anthropic-ai` -- the identities for systematic crawling -- are told `Disallow: /cmp/`.

This harness crawls a fixed list of 108 companies unattended and archives every page into a
durable evidence store. That is the second profile, not the first, so `AGENT_IDENTITIES`
checks the strictest group that plausibly describes this activity and takes the union of
what they forbid. Picking a user-agent string that fails to match a site's blocklist in
order to get through would be evasion, not compliance, and the archive would be built on
access the publisher declined to grant.

This module answers only "may this URL be fetched". A refusal is a `source_limitation` for
the caller to record as an attempt -- never a silent skip, because a source the harness was
forbidden to read and a source that genuinely held nothing are different facts and
convention 6a turns on telling them apart.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

# The identities whose rules this project must obey. The check takes the union of the
# groups matching any of these plus `*`, so the strictest applicable policy wins.
AGENT_IDENTITIES = ("ClaudeBot", "anthropic-ai", "Claude-User", "Claude-SearchBot")

USER_AGENT = ("Mozilla/5.0 (compatible; IndStudy-MarketIntel/1.0; "
              "academic research; +contact via repository)")
TIMEOUT = 20


@dataclass
class Policy:
    """Parsed robots.txt for one host."""

    host: str
    fetched: bool = False
    error: str = ""
    disallow: set = field(default_factory=set)
    crawl_delay: float = 0.0
    matched_groups: list = field(default_factory=list)

    def blocks(self, path: str) -> str:
        """Return the matching disallow rule, or "" if the path is permitted."""
        if not self.fetched:
            # A robots.txt that could not be fetched is not a licence. It is also not a
            # prohibition: the widely-followed reading is that an unreachable robots.txt
            # leaves the site open. Recorded so the caller can see the check was inconclusive.
            return ""
        best = ""
        for rule in self.disallow:
            if _match(rule, path) and len(rule) > len(best):
                best = rule
        return best


def _match(rule: str, path: str) -> bool:
    """robots.txt prefix matching with `*` wildcards and `$` anchoring."""
    if not rule:
        return False
    if rule == "/":
        return True
    anchored = rule.endswith("$")
    pattern = rule[:-1] if anchored else rule
    parts = pattern.split("*")
    pos = 0
    for i, part in enumerate(parts):
        if not part:
            continue
        if i == 0:
            if not path.startswith(part):
                return False
            pos = len(part)
            continue
        found = path.find(part, pos)
        if found == -1:
            return False
        pos = found + len(part)
    if anchored and len(parts) == 1:
        return path == pattern
    return True


def parse(text: str, identities=AGENT_IDENTITIES) -> tuple[set, float, list]:
    """Union of disallow rules across `*` and every matching agent identity."""
    groups: list[tuple[list, list]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    last_was_agent = False
    for raw in text.splitlines():
        line = raw.split("#")[0].strip()
        if ":" not in line:
            continue
        field_name, _, value = line.partition(":")
        field_name = field_name.strip().lower()
        value = value.strip()
        if field_name == "user-agent":
            if rules and not last_was_agent:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value)
            last_was_agent = True
        elif field_name in ("disallow", "allow", "crawl-delay"):
            rules.append((field_name, value))
            last_was_agent = False
    if agents or rules:
        groups.append((agents, rules))

    wanted = {a.lower() for a in identities} | {"*"}
    disallow: set = set()
    delay = 0.0
    matched: list = []
    for group_agents, group_rules in groups:
        names = {a.lower() for a in group_agents}
        if not (names & wanted):
            continue
        matched.append(sorted(names & wanted))
        for field_name, value in group_rules:
            if field_name == "disallow" and value:
                disallow.add(value)
            elif field_name == "crawl-delay":
                try:
                    delay = max(delay, float(value))
                except ValueError:
                    pass
    return disallow, delay, matched


class RobotsGate:
    """Per-host robots.txt cache and permission check."""

    def __init__(self, user_agent: str = USER_AGENT):
        self.user_agent = user_agent
        self._hosts: dict[str, Policy] = {}

    def policy(self, url: str) -> Policy:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower()
        if host in self._hosts:
            return self._hosts[host]
        policy = Policy(host=host)
        robots_url = f"{parsed.scheme or 'https'}://{host}/robots.txt"
        try:
            req = urllib.request.Request(
                robots_url, headers={"User-Agent": self.user_agent})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                body = r.read(500_000).decode("utf-8", "replace")
            policy.disallow, policy.crawl_delay, policy.matched_groups = parse(body)
            policy.fetched = True
        except urllib.error.HTTPError as e:
            # 404 means no robots.txt, which permits everything.
            policy.fetched = e.code == 404
            policy.error = f"HTTP {e.code}"
        except Exception as e:
            policy.error = f"{type(e).__name__}: {e}"
        self._hosts[host] = policy
        return policy

    def check(self, url: str) -> tuple[bool, str]:
        """Return (allowed, reason). `reason` is empty when allowed."""
        parsed = urllib.parse.urlparse(url)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        policy = self.policy(url)
        rule = policy.blocks(path)
        if rule:
            return False, (f"robots.txt on {policy.host} disallows {rule!r} for "
                           f"{'/'.join(sorted({a for g in policy.matched_groups for a in g}))}")
        return True, ""

    def allowed(self, url: str) -> bool:
        return self.check(url)[0]
