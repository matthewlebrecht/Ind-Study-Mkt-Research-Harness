#!/usr/bin/env python3
"""
Regression tests for entity resolution, written against failures that actually happened.

Every case in section 1 is a documented incident from this project's own record, not a
hypothetical. Entity resolution is the established primary failure surface and every
harness from here on shares this module, so a regression here is a regression everywhere.

    python core/tests/test_resolution.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import resolution as R  # noqa: E402

PASS = FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def named(*names):
    return [{"name": n} for n in names]


def main() -> int:
    print("1. documented Week 1 failures do not recur")

    # Substring matching pulled SOUTHWESTERN EXPRESS for "Western Express".
    r = R.resolve("Western Express",
                  named("SOUTHWESTERN EXPRESS INC", "WESTERN EXPRESS INC"),
                  name_of=lambda c: c["name"])
    check("Western Express resolves to WESTERN EXPRESS, not SOUTHWESTERN",
          r.resolved and r.winner.name == "WESTERN EXPRESS INC")
    check("SOUTHWESTERN scores far below, not marginally below",
          R.score("Western Express", "SOUTHWESTERN EXPRESS INC") < 0.4)
    check("the rejection is logged with its score",
          any(x["name"] == "SOUTHWESTERN EXPRESS INC" for x in r.as_log()["rejected"]))

    # Venture Logistics files as VENTURE TRANSPORT LLC.
    check("brand/registry divergence still clears the floor",
          R.score("Venture Logistics", "VENTURE TRANSPORT LLC") >= R.DEFAULT_FLOOR)

    # Kenco holds five co-located registrations under one company_id.
    kenco = named("KENCO LOGISTIC SERVICES LLC", "KENCO TRANSPORTATION SERVICES LLC")
    r = R.resolve("Kenco Group", kenco, name_of=lambda c: c["name"])
    check("co-located registrations are ambiguous, not silently one of them",
          r.status == "ambiguous")
    check("ambiguity routes to entity_ambiguous_multiple",
          r.failure_category == "entity_ambiguous_multiple")
    r = R.resolve("Kenco Group", kenco, name_of=lambda c: c["name"], accept_multiple=True)
    check("accept_multiple takes them all rather than picking arbitrarily",
          r.resolved and len(r.considered) == 2)

    print("\n2. the harness refuses rather than guessing")
    r = R.resolve("PLS Logistics", named("Pls Drywall And Ceilings Inc."),
                  name_of=lambda c: c["name"])
    check("an unrelated firm sharing one token is refused", not r.resolved)
    check("refusal routes to entity_below_threshold",
          r.failure_category == "entity_below_threshold")
    r = R.resolve("Anything", [], name_of=lambda c: c["name"])
    check("an empty candidate set is no_candidate, not below_threshold",
          r.status == "no_candidate" and r.failure_category == "entity_no_candidate")

    print("\n3. scoring properties that keep the above true")
    check("legal suffixes do not inflate a score",
          R.score("Duke Manufacturing", "DUKE MANUFACTURING CO") == 1.0)
    check("a weak industry token alone does not resolve",
          R.score("Acme Logistics", "Bravo Logistics") < R.DEFAULT_FLOOR)
    check("a long unrelated name containing the query is penalised",
          R.score("Mack", "MACK NORTHEAST REGIONAL DISTRIBUTION HOLDINGS") < 1.0)
    check("an empty name scores zero rather than raising",
          R.score("", "ANYTHING") == 0.0 and R.score("X", None) == 0.0)

    print("\n4. query variants are conservative")
    check("a trailing legal suffix is stripped",
          R.strip_legal_suffix("Duke Manufacturing Co.") == "Duke Manufacturing")
    check("stacked suffixes are stripped",
          R.strip_legal_suffix("Foo Holdings Company, Inc.") == "Foo Holdings")
    v = R.query_variants("PLS Logistics")
    check("no guessed abbreviation is generated (the 'PLS' drywall trap)",
          "PLS" not in v)
    v = R.query_variants("Mack Group", ["Mack Molding"])
    check("a human-seeded alias is included", "Mack Molding" in v)
    check("the full name is tried first", v[0] == "Mack Group")
    check("variants are de-duplicated case-insensitively",
          len(R.query_variants("Acme", ["ACME", "acme"])) == 1)

    print("\n5. state parsing (the 'Chicago, IL' -> 'CH' bug)")
    check("a bare code passes through", R.state_code("OH") == "OH")
    check("City, ST yields the state", R.state_code("Chicago, IL") == "IL")
    check("multi-word cities still work",
          R.state_code("Salt Lake City, UT") == "UT")
    check("an unrecognisable value yields empty, never a guess",
          R.state_code("Foreign Nation") == "" and R.state_code(None) == "")
    check("a two-letter non-state is not accepted", R.state_code("XX") == "")

    print(f"\n{PASS} checks passed, {FAIL} failed.")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
