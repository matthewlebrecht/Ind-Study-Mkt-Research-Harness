"""
Process-cause tests for H-PRODUCTQUALITY-01.

    python core/tests/test_productquality.py

The first case is the whole reason v1.1 exists. v1.0 produced two observations across the
entire universe and one of them was wrong: a MAUDE narrative in which Midmark's ECG
software CORRECTLY detected a myocardial infarction was scored as a systems failure on the
bare token "SOFTWARE", and written as a `legacy_constraint` row asserting the opposite of
what the record says.

It was found by reading two rows, not by a test. That is convention 33 working, and this
file is the part that stops it coming back.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harnesses.h_productquality_01 import sources  # noqa: E402

PASSED = FAILED = 0


def check(cond, label):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok    {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label}")


# Verbatim from openFDA MAUDE report 2081230-2020-00001, the row v1.0 got wrong.
MIDMARK_ECG = (
    "THE FILE WAS ANALYZED BY THE PRINCIPLE BIOMEDICAL ENGINEER AT MIDMARK. THE FILE WAS "
    "REVIEWED, AND THE PATIENT HAD ANTERIOR MYOCARDIAL INFARCTION WHICH THE SOFTWARE HAD "
    "DETECTED. MIDMARK'S PHYSICIAN'S GUIDE STATES: WHEN THE EVIDENCE OF ABNORMALITY IS ON "
    "THE BORDERLINE WITH SIGNAL ARTIFACTS, HUMAN INTERPRETATION IS REQUIRED."
)

# Verbatim from openFDA device recalls 75127 and 83738 (Merit Medical), which are real.
MERIT_LABELS = "unit labels missing required device labeling information"
MERIT_LATEX = ("Labeling error; It was identified that a Procedure Kit/Tray contained "
               "incorrect latex labeling information (i.e. indicated Latex Free)")


def main() -> int:
    print("1. a cue word is not a cause (the v1.0 defect)")
    check(sources.process_cause(MIDMARK_ECG) is None,
          "software that WORKED is not a systems failure, however often 'SOFTWARE' appears")
    check(sources.PROCESS_CAUSE_RE.search(MIDMARK_ECG) is not None,
          "...and the cue really does fire -- it is the failure predicate that saves it, "
          "so this is an admission test and not a lucky pattern")
    check(sources.process_cause("The device uses proprietary software for imaging.") is None,
          "a system merely being mentioned is not a system failing")

    print("\n2. real systems causes are still admitted")
    for text, label in [(MERIT_LABELS, "labels missing required information"),
                        (MERIT_LATEX, "labeling error / incorrect information")]:
        got = sources.process_cause(text)
        check(got is not None, f"admitted: {label}")
    got = sources.process_cause(
        "The firm's electronic batch record system did not capture the deviation.")
    check(got is not None and got[0] == "erp_core_systems",
          "a batch-record failure maps to ERP and core systems, not to a generic theme")
    got = sources.process_cause(
        "Product was released before the sterilization cycle validation failed to complete.")
    check(got is not None, "a validation failure is a process cause")

    print("\n3. ordinary recalls generate nothing")
    for text in ["Possible stainless steel pieces in product.",
                 "The plastic housing may crack during normal use.",
                 "Product may contain undeclared milk.",
                 "Units were distributed with a cracked luer fitting."]:
        check(sources.process_cause(text) is None, f"not a systems cause: {text[:52]}")

    print("\n4. the predicate has to be in the SAME sentence as the cue")
    check(sources.process_cause(
        "The device includes control software. The plastic housing was defective.") is None,
        "a system in one sentence and a fault in another is not a systems cause")
    check(sources.process_cause(
        "The control software was defective.") is not None,
        "the same two facts in one sentence are")

    print("\n5. dates are normalised, never guessed")
    check(sources._iso("20201027") == "2020-10-27", "YYYYMMDD becomes ISO")
    check(sources._iso("2018-10-26") == "2018-10-26", "ISO passes through")
    check(sources._iso("n/a") == "" and sources._iso(None) == "",
          "an unparseable date yields empty, never a fabricated one (convention 3)")

    print("\n6. a server error served as HTTP 200 is a failure, not an empty result")
    try:
        sources.normalise("cpsc_recall", [{
            "Title": "Error retrieving Recalls: The underlying provider failed on Open."}])
        check(False, "CPSC error record raises rather than returning no recalls")
    except sources.SourceError as e:
        check("error record" in str(e).lower(),
              "CPSC error record raises rather than returning no recalls")
    rows = sources.normalise("cpsc_recall", [{
        "Title": "Scentsy Recalls Electrical Oil Warmers Due to Fire Hazard",
        "RecallDate": "2020-12-10T00:00:00", "RecallNumber": "21712",
        "Description": "This recall involves electrical warmers.", "Manufacturers": []}])
    check(len(rows) == 1 and "Scentsy" in rows[0]["firm"],
          "a real CPSC record identifies the firm from the title when Manufacturers is empty")

    print("\n7. openFDA 404 means 'no matching records', not 'could not look'")
    check(sources.normalise("openfda_device_recall", {"results": [], "_empty": True}) == [],
          "an empty result set normalises to no events without raising")

    print(f"\n{PASSED} checks passed, {FAILED} failed.")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
