#!/usr/bin/env python3
"""
Probe a candidate API source and record what actually happened, reproducibly.

WHY THIS IS A SCRIPT AND NOT A HARNESS
--------------------------------------
H-EMPREVIEW-01 established that an access refusal is a determinate outcome and belongs in
the database alongside `absent_confirmed`, not in prose. That is right *when the refusal is
the source's own decision* -- Glassdoor publishes `Disallow: /` for this crawler identity,
and 107 `access_blocked` attempt rows citing it are true statements about the source.

It is wrong when the failure might be local. On 2026-08-31 two of the four Priority-2 API
sources failed here in ways that do not distinguish a source policy from this machine's
network:

    api.usaspending.gov     TLS: "self-signed certificate in certificate chain".
                            Every other HTTPS host in the run verified fine, so this is
                            most likely a TLS-intercepting middlebox on one route rather
                            than anything USASpending did. From another network it would
                            probably just work.
    search.patentsview.org  DNS does not resolve. api.patentsview.org resolves but serves
                            an HTML application shell instead of JSON, which is what a
                            moved or key-gated API looks like from outside.

Writing 108 `access_blocked` attempts from either of those would put a claim about a
federal source into the evidence base on the strength of a local network condition. That is
the same class of error as recording a CPSC server fault as `absent_confirmed`, pointed the
other way, and convention 6a rates a false record worse than a gap.

So the probe records the evidence and writes nothing to the workbook. Re-run it from a
different network; if a source still fails there, the failure is the source's and a harness
can then record it honestly.

    python scripts/probe_sources.py
    python scripts/probe_sources.py --json

WHAT 2026-09-01 CHANGED
-----------------------
The 2026-08-31 run attributed `api.usaspending.gov` to "a TLS-intercepting middlebox".
That was wrong, and it was wrong because this script measured a client stack no harness
uses -- convention 36, a lookup answering confidently about the wrong question.

  * The probe verified with `urllib` + `ssl.create_default_context()`, which on Windows
    trusts the **Windows ROOT store**. Every harness fetches with `requests`, which trusts
    **certifi**. The Windows store on this machine carries 40 roots and does not include
    `Sectigo Public Server Authentication Root R46`; certifi does. USASpending serves a
    genuine Department of Treasury leaf issued by Entrust chaining to that Sectigo root, so
    it fails in the probe's store and verifies fine in the harnesses'. No interception was
    involved: an intercepting middlebox forges a leaf under a local root, and this leaf is
    authentic.
  * Once TLS verified, every USASpending endpoint returned an HTTP 500 carrying a network
    filter interstitial -- "Web Page Blocked", naming this machine's own egress IP and an
    "Attack ID". The old code classified that as `http_error` / "could be the source or a
    transient fault". It is neither: it is a local block, and the page says so in its own
    words.

So the probe now fetches through the same stack the harnesses do, and detects filter
interstitials explicitly. The 2026-08-31 *decision* -- write nothing to the workbook --
was right for the wrong reason, and is now right for a citable one.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import requests

try:
    import certifi
except ImportError:  # pragma: no cover - certifi ships with requests
    certifi = None

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "harness_output" / "_source_probes"

# The harnesses' own identity, not a probe-only one. 2026-09-13: the probe's previous UA,
# "IndStudyResearchBot/1.0 (...)", was the entire USASpending "block". USASpending's
# server-side web application firewall (behind its F5 load balancer, answering inside a
# TLS session verified against Treasury's own Entrust certificate) matches the token
# "ResearchBot" and serves a "Web Page Blocked!" page with an Attack ID under HTTP 500. The
# same request with this UA, a browser UA, python-requests' default or no UA at all gets
# 200 from the same egress IP. The 2026-09-01 reading -- "a network appliance on this
# egress" -- was convention 36 again: the page echoes the client IP, which reads like a
# local filter, but a local appliance cannot answer inside a verified TLS session.
UA = "Mozilla/5.0 (compatible; IndStudy-MarketIntel/1.0; +independent study, contact via repo)"
TIMEOUT = 45

# (label, url, body-or-None, what a success proves)
PROBES = [
    ("usaspending", "https://api.usaspending.gov/api/v2/references/toptier_agencies/",
     None, "H-PROCUREMENT-01 (task 5) -- federal award records"),
    ("sam_gov", "https://api.sam.gov/entity-information/v3/entities?samRegistered=Yes",
     None, "H-PROCUREMENT-01 (task 5) -- entity registration; expected to need a key"),
    # PatentsView is RETIRED at the source, not blocked here (attributed 2026-09-13). USPTO
    # shut the PatentSearch API down on 2026-03-20 and moved PatentsView to the Open Data
    # Portal (data.uspto.gov); the host was removed from public DNS (NXDOMAIN from the
    # system resolver AND from Cloudflare DoH, so not a local resolver), and patentsview.org
    # / api.patentsview.org now redirect to data.uspto.gov/support/transition-guide/
    # patentsview. Kept as probes so a return of the host is noticed; a replacement path is
    # not guessed here (convention 36's NLRB lesson: invented API paths are not a probe).
    ("patentsview_search", "https://search.patentsview.org/api/v1/patent/?q=%7B%7D",
     None, "H-PATENTS-01 -- PatentSearch API, retired by USPTO 2026-03-20 (expect dns_failure)"),
    ("patentsview_legacy", "https://api.patentsview.org/patents/query?q=%7B%7D",
     None, "H-PATENTS-01 -- legacy host, now redirects to the ODP transition guide"),
    ("courtlistener", "https://www.courtlistener.com/api/rest/v4/search/?q=test&type=r",
     None, "H-LEGAL-01 (task 8) -- federal dockets"),
    # Expects text, not JSON -- see EXPECT_TEXT below.
    ("nlrb", "https://www.nlrb.gov/robots.txt",
     None, "H-LEGAL-01 (task 8) -- NLRB case data, access policy"),
    ("openfda", "https://api.fda.gov/device/recall.json?limit=1",
     None, "H-PRODUCTQUALITY-01 -- control probe, known working"),
]


# Probes that legitimately return something other than JSON. Without this the robots.txt
# probe reports `html_shell_not_json`, which is a false description of a successful fetch --
# a mislabelled outcome in the one script whose entire job is labelling outcomes correctly.
EXPECT_TEXT = {"nlrb"}


# A network filter answers *for* the host, with a page of its own, under whatever status
# code it likes. Left undetected it reads as the source erroring. These markers are the
# literal wording of such interstitials; they are deliberately specific phrases rather than
# a bare "blocked", because a loose marker here would misattribute real source errors to
# the network -- convention 16, in the one script whose whole job is attribution.
BLOCK_MARKERS = (
    "web page blocked",
    "the url you requested has been blocked",
    "attack id",
    "this website has been blocked",
    "access denied by your network",
    "blocked by your organization",
)


def _filter_interstitial(text, content_type):
    """Return the marker identifying `text` as a network filter page, else None.

    Requires an HTML body: a JSON API whose legitimate payload happens to contain the
    word "blocked" must not be mistaken for an interstitial.
    """
    if "html" not in (content_type or "").lower():
        return None
    low = text.lower()
    for marker in BLOCK_MARKERS:
        if marker in low:
            return marker
    return None


def _trust_store_report(host):
    """Record which trust stores accept `host`, rather than picking one silently.

    The 2026-08-31 misattribution came from reporting one store's verdict as though it
    were the network's. Both are recorded now so a divergence is visible instead of
    being resolved by whichever library the script happened to import.
    """
    out = {}
    stores = [("os_default", ssl.create_default_context())]
    if certifi is not None:
        stores.append(("certifi", ssl.create_default_context(cafile=certifi.where())))
    else:
        out["certifi"] = "unavailable"
    for name, ctx in stores:
        try:
            with socket.create_connection((host, 443), timeout=15) as sock:
                with ctx.wrap_socket(sock, server_hostname=host):
                    out[name] = "verified"
        except ssl.SSLError as exc:
            out[name] = "tls_failure: " + str(exc)[:90]
        except Exception as exc:
            out[name] = type(exc).__name__ + ": " + str(exc)[:70]
    return out


def probe(label: str, url: str, body) -> dict:
    host = urllib.parse.urlparse(url).netloc
    rec = {"label": label, "url": url, "host": host}
    try:
        rec["dns"] = socket.gethostbyname(host)
    except OSError as e:
        rec["dns"] = None
        rec["outcome"] = "dns_failure"
        rec["detail"] = f"{type(e).__name__}: {e}"
        return rec

    # Fetch through the same stack the harnesses use (`requests`, hence certifi), not
    # urllib's OS-store default. Probing a different trust store than the harnesses trust
    # is how 2026-08-31 reported a source failure no harness would ever have seen.
    rec["trust_stores"] = _trust_store_report(host)

    headers = {"User-Agent": UA, "Accept": "application/json",
               "Content-Type": "application/json"}
    try:
        if body is None:
            resp = requests.get(url, headers=headers, timeout=TIMEOUT)
        else:
            resp = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
    except requests.exceptions.SSLError as exc:
        rec["outcome"] = "tls_failure"
        rec["detail"] = str(exc)[:200]
        return rec
    except requests.exceptions.RequestException as exc:
        rec["outcome"] = "network_failure"
        rec["detail"] = "{}: {}".format(type(exc).__name__, exc)[:200]
        return rec

    head = resp.text[:1500]
    ctype = resp.headers.get("Content-Type", "")
    rec["status"] = resp.status_code
    rec["content_type"] = ctype

    marker = _filter_interstitial(head, ctype)
    if marker is not None:
        # The filter answered instead of the host, so whatever status it chose says
        # nothing whatever about the source.
        flat = re.sub(r"<[^>]+>", " ", head)
        flat = re.sub(r"\s+", " ", flat).strip()
        rec["outcome"] = "blocked_by_local_filter"
        rec["block_marker"] = marker
        rec["detail"] = flat[:200]
        return rec

    if resp.status_code >= 400:
        rec["outcome"] = ("auth_required" if resp.status_code in (401, 403)
                          else "not_found" if resp.status_code == 404
                          else "http_error")
        rec["detail"] = head[:200].replace("\n", " ")
        return rec

    # A 200 serving HTML where JSON was asked for is a moved or gated API, not a working
    # one. Reporting it as reachable would be the same mistake as reading CPSC's error
    # record as an empty result set.
    looks_json = head.lstrip().startswith(("{", "["))
    rec["outcome"] = ("ok" if (looks_json or label in EXPECT_TEXT)
                      else "html_shell_not_json")
    rec["detail"] = head[:200].replace("\n", " ")
    return rec


# Which outcomes are safe to record in the database as a claim about the SOURCE, and which
# are not. This mapping is the whole point of the script.
ATTRIBUTION = {
    "ok": ("source", "reachable"),
    "auth_required": ("source", "the source requires credentials -- a real, citable policy"),
    "html_shell_not_json": ("source", "the API endpoint has moved or is gated"),
    "not_found": ("source", "the endpoint does not exist at this path"),
    "http_error": ("ambiguous", "could be the source or a transient fault"),
    "tls_failure": ("LOCAL, probably", "the chain did not verify in the store this run "
                                       "used; compare the two `trust_stores` verdicts "
                                       "and read the issuer before blaming the source. "
                                       "An authentic leaf under an untrusted-here root "
                                       "is a trust-store gap, not interception"),
    "blocked_by_local_filter": ("LOCAL, confirmed", "a network appliance served its own "
                                                    "page instead of the host's; the "
                                                    "interstitial names the blocking "
                                                    "policy and this machine's egress IP. "
                                                    "Never a claim about the source"),
    "dns_failure": ("ambiguous", "the host may not exist, or DNS may be filtered here"),
    "network_failure": ("ambiguous", "transient or local"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    stamp = _dt.date.today().isoformat()
    results = [probe(label, url, body) for label, url, body, _why in PROBES]
    why = {label: w for label, _u, _b, w in PROBES}

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"probe-{stamp}.json"
    path.write_text(json.dumps({"date": stamp, "results": results}, indent=2),
                    encoding="utf-8")

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    print(f"source probes, {stamp}\n")
    for r in results:
        attr, note = ATTRIBUTION.get(r["outcome"], ("ambiguous", ""))
        print(f"  {r['label']:20s} {r['outcome']:22s} [{attr}]")
        print(f"      {why[r['label']]}")
        print(f"      {r.get('detail', '')[:120]}")
        stores = r.get("trust_stores") or {}
        if len(set(stores.values())) > 1:
            print(f"      trust stores DIVERGE: "
                  + "; ".join(f"{k}={v[:48]}" for k, v in stores.items()))
        if r.get("block_marker"):
            print(f"      filter marker matched: {r['block_marker']!r}")
        if attr.startswith("LOCAL"):
            print(f"      !! {note}")
        print()
    print(f"written to {path}")
    print("\nNothing was written to the workbook. A failure that might be local is not a "
          "claim about a source,\nand recording one as `access_blocked` would put a false "
          "statement about a federal database into\nthe evidence base (convention 6a).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
