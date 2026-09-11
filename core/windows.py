"""
The evidence-staleness standard, in one place.

Decided by Matthew on 2026-09-03 (session 10 brief, item 1): FIVE YEARS, everywhere.
Earlier documents stated a 36-month project standard while both harnesses that enforce
a window (H-FIRSTPARTY-01, H-TRADEPRESS-01) already used five years; the inconsistency is
resolved in favour of the existing, more permissive window, and any other setting is
overwritten rather than kept as a second parallel value. A harness that reports a
recency SUBSET inside an observation (H-SAFETY-ENV-01's 36-month count) is not a
staleness gate and is untouched.

An announcement older than this is excluded from the evidence base and reported as a
governance suppression (`stale_beyond_threshold`), never dropped silently.
"""

STALENESS_YEARS = 5
MAX_AGE_DAYS = 365 * STALENESS_YEARS
