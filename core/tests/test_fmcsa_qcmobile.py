#!/usr/bin/env python3
"""
H-FMCSA-01 QCMobile field mappings (v1.6) and the SAFER+QCMobile hybrid snapshot (v1.7).

    python core/tests/test_fmcsa_qcmobile.py

Pins the two mappings corrected on 2026-09-15 and, more importantly, pins the DISTINCTION
they exist to protect. QCMobile's `allowedToOperate` is the USDOT registration status, not
for-hire authority; reading authority from it made a private fleet -- which by definition
holds no for-hire authority and which SAFER reports as "NOT AUTHORIZED" -- come back
"AUTHORIZED". That is the same private-versus-for-hire distinction `_is_private_carriage`
exists for, and it is the difference between recording an expected state and manufacturing a
compliance gap.

Payloads below are trimmed copies of the shapes the live API returned on 2026-09-15 for
Midmark (USDOT 3462870, private carriage) and Western Express (USDOT 511412, for hire).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from harnesses.h_fmcsa_01.source import (  # noqa: E402
    FmcsaClient, _authorities, _parse_qcmobile)

PASS = FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def payload(**over):
    base = {
        "dotNumber": 3462870, "legalName": "MIDMARK CORPORATION", "dbaName": None,
        "allowedToOperate": "Y", "statusCode": "A",
        "carrierOperation": {"carrierOperationCode": "A", "carrierOperationDesc": "Interstate"},
        "censusTypeId": {"censusType": "C", "censusTypeDesc": "CARRIER", "censusTypeId": 1},
        "commonAuthorityStatus": None, "contractAuthorityStatus": None,
        "brokerAuthorityStatus": None,
        "totalPowerUnits": 2, "totalDrivers": 1, "safetyRating": "S",
        "safetyRatingDate": "1993-05-20", "vehicleInsp": 0, "driverInsp": 0,
        "vehicleOosRate": 0, "driverOosRate": 0,
        "vehicleOosRateNationalAverage": "20.72", "driverOosRateNationalAverage": "5.51",
        "fatalCrash": 0, "injCrash": 0, "towawayCrash": 1, "crashTotal": 1,
    }
    base.update(over)
    return {"content": {"carrier": base}}


def main() -> int:
    # --- the authority collapse itself -------------------------------------------------
    check("no authority field set -> holds none",
          _authorities({}) == [])
    check("only inactive authority -> holds none (I is not A)",
          _authorities({"commonAuthorityStatus": "I", "brokerAuthorityStatus": "I"}) == [])
    check("active common + contract -> both, in SAFER's order",
          _authorities({"commonAuthorityStatus": "A", "contractAuthorityStatus": "A",
                        "brokerAuthorityStatus": "I"}) == ["Common", "Contract"])
    check("lowercase 'a' and stray whitespace still count as active",
          _authorities({"brokerAuthorityStatus": " a "}) == ["Broker"])

    # --- private carriage: the case the old mapping got wrong ---------------------------
    private = _parse_qcmobile(payload())
    check("private fleet reads NOT AUTHORIZED even though allowedToOperate is 'Y'",
          private["operating_authority_status"] == "NOT AUTHORIZED")
    check("private fleet names no authority",
          private["authorized_for"] is None)
    check("USDOT registration status is still ACTIVE -- the two are different questions",
          private["usdot_status"] == "ACTIVE")
    check("entity type comes from censusTypeId.censusTypeDesc",
          private["entity_type"] == "CARRIER")
    check("jurisdiction is NOT mistaken for authority",
          private["authorized_for"] != "Interstate"
          and private["carrier_operation"] == ["Interstate"])

    # --- for-hire carrier ---------------------------------------------------------------
    forhire = _parse_qcmobile(payload(
        dotNumber=511412, legalName="WESTERN EXPRESS INC",
        commonAuthorityStatus="A", contractAuthorityStatus="A", brokerAuthorityStatus="I"))
    check("for-hire carrier reads AUTHORIZED",
          forhire["operating_authority_status"] == "AUTHORIZED")
    check("for-hire carrier names the active authorities only",
          forhire["authorized_for"] == "Common, Contract")

    # --- a revoked for-hire carrier is NOT the same as a private one --------------------
    revoked = _parse_qcmobile(payload(
        commonAuthorityStatus="I", contractAuthorityStatus="I"))
    check("every authority inactive reads NOT AUTHORIZED",
          revoked["operating_authority_status"] == "NOT AUTHORIZED")

    # --- the source gap that remains, pinned so it cannot be forgotten ------------------
    # QCMobile's censusTypeDesc is single-valued. SAFER composes multi-role entity types
    # ("CARRIER/SHIPPER", "CARRIER/SHIPPER/BROKER") and a pure broker carries no
    # censusTypeId at all. Measured 2026-09-15: entity_type differs from the committed
    # SAFER-derived rows on 4 of the 8 carriers that resolve. This is a real difference
    # between the two sources, not a parse bug, and the harness must not pretend otherwise.
    broker = _parse_qcmobile(payload(dotNumber=4037747, censusTypeId=None,
                                     brokerAuthorityStatus="A"))
    check("a record with no censusTypeId yields entity_type None, not a guess",
          broker["entity_type"] is None)
    check("that record still resolves its authority correctly",
          broker["authorized_for"] == "Broker")

    # --- numeric coercion still holds (the v1.6 string-rate fix) ------------------------
    check("national-average rates served as strings are coerced",
          isinstance(private["vehicle_natl_avg_pct"], float)
          and private["vehicle_natl_avg_pct"] == 20.72)

    # --- v1.7 hybrid: SAFER record, QCMobile counts overlaid ----------------------------
    import json as _json
    import harnesses.h_fmcsa_01.source as S

    class FakeCache:
        def __init__(self, bodies, partitions, today="2026-09-16"):
            self.bodies, self.replayed_from, self.retrieval_date = bodies, partitions, today

        def get(self, key, suffix, fetch):
            b = self.bodies.get(key)
            if isinstance(b, Exception):
                raise b
            return b, True

    safer_rec = {"found": True, "dot_number": "511412", "entity_type": "CARRIER/SHIPPER/BROKER",
                 "operating_authority_status": "AUTHORIZED",
                 "authorized_for": "Motor Carrier of Property (Except Household Goods)",
                 "operation_classification": ["Auth. For Hire"], "data_as_of": "09/15/2026",
                 "power_units": 3332, "vehicle_oos_pct": 30.5, "vehicle_natl_avg_pct": 22.26,
                 "vehicle_oos": 2243}

    def hybrid(qc_body, partitions=None, webkey="k"):
        c = FmcsaClient.__new__(FmcsaClient)
        c.webkey = webkey
        c.cache = FakeCache({"safer_511412": "<html/>", "qc_511412": qc_body}, partitions or {})
        orig = S.parse_safer_snapshot
        S.parse_safer_snapshot = lambda body: dict(safer_rec)
        try:
            return c.carrier_snapshot("511412")
        finally:
            S.parse_safer_snapshot = orig

    qc = _json.dumps(payload(dotNumber=511412, commonAuthorityStatus="A", contractAuthorityStatus="A",
                             totalPowerUnits=3340, vehicleOosRate=30.495969394726057,
                             vehicleOosInsp=2250))
    h = hybrid(qc)
    check("hybrid: SAFER's entity type survives the overlay", h["entity_type"] == "CARRIER/SHIPPER/BROKER")
    check("hybrid: SAFER's authority scope survives the overlay",
          h["authorized_for"] == "Motor Carrier of Property (Except Household Goods)")
    check("hybrid: SAFER's classification and data date survive",
          h["operation_classification"] == ["Auth. For Hire"] and h["data_as_of"] == "09/15/2026")
    check("hybrid: QCMobile's counts are overlaid", h["power_units"] == 3340 and h["vehicle_oos"] == 2250)
    check("hybrid: a QCMobile rate is rounded to SAFER's one decimal", h["vehicle_oos_pct"] == 30.5)
    check("hybrid: a rate equal after rounding is not a disagreement",
          "vehicle_oos_pct" not in h.get("_source_disagreements", {}))
    check("hybrid: a real disagreement is overlaid AND recorded",
          h["_source_disagreements"]["power_units"] == {"safer": 3332, "qcmobile": 3340})
    check("hybrid: the national average never comes from QCMobile's 2009-2010 benchmark",
          h["vehicle_natl_avg_pct"] == 22.26)
    check("hybrid: provenance names both sources", h["_source"] == "safer+qcmobile")
    sk = hybrid(qc, partitions={"safer_511412": "2026-09-05", "qc_511412": "2026-09-06"})
    check("hybrid: responses from different dated partitions are not mixed",
          sk["power_units"] == 3332 and "2026-09-05" in sk["_numeric_overlay_skipped"])
    wr = hybrid(_json.dumps(payload(dotNumber=999, totalPowerUnits=1)))
    check("hybrid: a QCMobile record for another USDOT is refused",
          wr["power_units"] == 3332 and "999" in wr["_qcmobile_error"])
    er = hybrid(RuntimeError("offline mode and no archived response for qc_511412"))
    check("hybrid: a QCMobile failure leaves the SAFER record whole and says so",
          er["_source"] == "safer" and er["power_units"] == 3332 and "RuntimeError" in er["_qcmobile_error"])
    nk = hybrid(qc, webkey=None)
    check("hybrid: with no webkey the record is SAFER alone",
          nk["_source"] == "safer" and nk["power_units"] == 3332)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
