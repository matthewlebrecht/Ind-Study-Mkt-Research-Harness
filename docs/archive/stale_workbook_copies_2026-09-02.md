# Stale workbook copies — what they were, before deletion (2026-09-02)

**Why this record exists.** Sessions 5 and 6 spent time on an "O00366 is missing" alarm
that turned out to be someone opening the wrong file. `data/` held 32 gitignored
`market_intel_db.bak-<timestamp>.xlsx` copies beside the live workbook, auto-created by
`migrate_schema.py`, `register_sources.py`, `extend_validation.py` and
`reconstruct_workbook.py` on every `--apply`, and never pruned. Near-identical names, same
folder, no warning. Matthew's decision (post-session-6 brief, item 2): delete them, but
record what they held first, so the next "where did something go wrong" question can be
answered from this table rather than from a file that no longer exists.

Session 6 counted 31. There were 32 at deletion time: the newest, `bak-20260902-194027`,
was created by the Part B schema migration's `--apply` on 2026-09-02 at 19:40, after the
count was taken. It is byte-identical to the workbook committed at `c00944c`.

**How to read the table.**

- `filename ts` is when the `--apply` ran (the copy was taken *before* the write).
- `mtime` is older than the filename on most rows because `shutil.copy2` preserves the
  source file's modification time: it is when the live workbook had last been **saved**
  before that `--apply`. So `bak-20260831-093119` (mtime 08-30 23:11) is the workbook as
  it stood at the end of the 08-30 session, copied the next morning.
- `git` names the commit whose `data/market_intel_db.xlsx` blob is **byte-identical** to
  the copy. 12 of the 32 match a commit; those held nothing git did not already hold. The
  other 20 are intermediate states between commits: mid-session snapshots taken between
  one harness run and the next.
- `PQ` is the count of `H-PRODUCTQUALITY-01` observations; `O366` whether O00366 (the
  audited, human-corrected Merit Medical row) is present; `human` the count of rows with
  a human `review_status`. **22 of the 32 predate O00366 and show PQ = 0.** Those, plus
  the 7 archive copies (all pre-repository), are the 29 session 6 counted.
- `Comp` moves 108 → 120 at `bak-20260830-223904`: that is the 2026-08-30 22:39
  registration of the 12 provider rows `P001`–`P012` (`qualification_status =
  provider_benchmark`) for H-SELLERCONTENT-01, recorded in `SESSION_REPORT_2026-08-30.md`.
  The buyer universe was 108 before it and 108 after it.
- `-1` means the sheet did not exist yet in that copy.

## The 32 deleted `.bak-*` copies (`data/`, gitignored, 7.6 MB total)

| file | mtime | KB | Comp | Obs | Att | Runs | Exec | PQ | O366 | human | git |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `bak-20260830-222833` | 2026-08-30 22:25 | 34 | 108 | 35 | -1 | 5 | -1 | 0 | 0 | 27 | – |
| `bak-20260830-223236` | 2026-08-30 22:28 | 38 | 108 | 35 | 0 | 5 | 0 | 0 | 0 | 27 | – |
| `bak-20260830-223532` | 2026-08-30 22:32 | 39 | 108 | 35 | 0 | 5 | 0 | 0 | 0 | 27 | – |
| `bak-20260830-223540` | 2026-08-30 22:35 | 39 | 108 | 35 | 0 | 5 | 0 | 0 | 0 | 27 | – |
| `bak-20260830-223904` | 2026-08-30 22:39 | 45 | **120** | 73 | 12 | 6 | 0 | 0 | 0 | 27 | – |
| `bak-20260830-223943` | 2026-08-30 22:39 | 47 | 120 | 83 | 24 | 7 | 0 | 0 | 0 | 27 | – |
| `bak-20260830-230035` | 2026-08-30 23:00 | 106 | 120 | 214 | 452 | 9 | 0 | 0 | 0 | 27 | – |
| `bak-20260830-230052` | 2026-08-30 23:00 | 106 | 120 | 214 | 452 | 9 | 0 | 0 | 0 | 27 | – |
| `bak-20260830-230126` | 2026-08-30 23:01 | 108 | 120 | 209 | 464 | 10 | 0 | 0 | 0 | 27 | – |
| `bak-20260830-230623` | 2026-08-30 23:01 | 108 | 120 | 209 | 464 | 10 | 0 | 0 | 0 | 27 | – |
| `bak-20260830-231121` | 2026-08-30 23:10 | 130 | 120 | 228 | 678 | 12 | 0 | 0 | 0 | 27 | – |
| `bak-20260831-093119` | 2026-08-30 23:11 | 130 | 120 | 228 | 678 | 12 | 0 | 0 | 0 | 27 | `6b97d0b` |
| `bak-20260831-095826` | 2026-08-31 09:46 | 209 | 120 | 228 | 786 | 13 | 814 | 0 | 0 | 27 | – |
| `bak-20260831-102755` | 2026-08-31 10:27 | 223 | 120 | 228 | 1002 | 15 | 814 | 0 | 0 | 27 | – |
| `bak-20260831-185257` | 2026-08-31 10:35 | 295 | 120 | 315 | 1646 | 19 | 814 | 0 | 0 | 27 | `ad11785` |
| `bak-20260831-185329` | 2026-08-31 18:52 | 295 | 120 | 315 | 1646 | 19 | 814 | 0 | 0 | 27 | – |
| `bak-20260831-224959` | 2026-08-31 18:53 | 296 | 120 | 315 | 1646 | 19 | 814 | 0 | 0 | 27 | `fd71292` |
| `bak-20260831-225943` | 2026-08-31 22:50 | 299 | 120 | 315 | 1646 | 19 | 814 | 0 | 0 | 27 | `65bb2c4` |
| `bak-20260831-230045` | 2026-08-31 22:59 | 299 | 120 | 315 | 1646 | 19 | 814 | 0 | 0 | 27 | – |
| `bak-20260831-233320` | 2026-08-31 23:33 | 311 | 120 | 317 | 1769 | 21 | 814 | 0 | 0 | 27 | – |
| `bak-20260831-234409` | 2026-08-31 23:33 | 311 | 120 | 317 | 1769 | 21 | 814 | 0 | 0 | 27 | `45ef4a8` |
| `bak-20260831-234449` | 2026-08-31 23:44 | 311 | 120 | 317 | 1769 | 21 | 814 | 0 | 0 | 27 | – |
| `bak-20260901-110847` | 2026-09-01 11:08 | 344 | 120 | 318 | 2201 | 25 | 814 | **1** | **1** | 27 | `f109174` |
| `bak-20260901-124213` | 2026-09-01 12:35 | 353 | 120 | 318 | 2309 | 26 | 814 | 1 | 1 | 30 | `053d84d` |
| `bak-20260901-125726` | 2026-09-01 12:42 | 353 | 120 | 318 | 2309 | 26 | 814 | 1 | 1 | 30 | – |
| `bak-20260901-130311` | 2026-09-01 12:58 | 363 | 120 | 319 | 2417 | 27 | 814 | 1 | 1 | 30 | `830fa82` |
| `bak-20260901-143830` | 2026-09-01 14:38 | 395 | 120 | 320 | 2801 | 31 | 814 | 1 | 1 | 30 | – |
| `bak-20260901-143854` | 2026-09-01 14:38 | 395 | 120 | 320 | 2801 | 31 | 814 | 1 | 1 | 30 | – |
| `bak-20260901-155614` | 2026-09-01 15:36 | 396 | 120 | 320 | 2801 | 31 | 814 | 1 | 1 | 39 | `310e244` |
| `bak-20260901-161133` | 2026-09-01 15:58 | 396 | 120 | 320 | 2801 | 31 | 814 | 1 | 1 | 39 | `73b6c24` |
| `bak-20260901-163229` | 2026-09-01 16:32 | 417 | 120 | 333 | 3015 | 32 | 814 | 1 | 1 | 39 | – |
| `bak-20260902-194027` | 2026-09-01 16:52 | 473 | 120 | 337 | 3659 | 37 | 814 | 1 | 1 | 39 | `c00944c` |

Filenames are abbreviated: each is `data/market_intel_db.<file>.xlsx`.

## The 7 retained copies (`data/archive/`, tracked, 188 KB total)

| file | mtime | KB | Comp | Obs | Runs | human | note |
|---|---|---:|---:|---:|---:|---:|---|
| `STALE-2026-08-26` | 2026-08-30 22:19 | 32 | 109 | 2 | 2 | 0 | the pre-cleanup copy the Anvil import landed in; `reconstruct_workbook.py` STALE input |
| `backup-20260822-202854` | 2026-08-22 20:28 | 21 | 9 | 2 | 2 | 0 | earliest copy |
| `backup-pre-jobpost-231246` | 2026-08-24 23:12 | 23 | 8 | 27 | 4 | 27 | `reconstruct_workbook.py` BASE input |
| `backup-pre-v11-205241` | 2026-08-22 20:52 | 23 | 8 | 27 | 1 | 0 | before H-FMCSA-01 v1.1 |
| `backup-pre-v12-214521` | 2026-08-22 21:45 | 23 | 8 | 27 | 2 | 0 | last copy with the 9 data validations intact |
| `backup-pre-v13-224546` | 2026-08-24 22:45 | 27 | 8 | 27 | 3 | 27 | first copy without them |
| `backup-pre-venture-225842` | 2026-08-24 22:58 | 22 | 8 | 27 | 4 | 27 | before the Venture Logistics correction |

None of these has an `Attempts` or `Company_Executives` sheet; none holds a
`H-PRODUCTQUALITY-01` row. They are kept tracked, and why is in `data/archive/README.md`.

## What changed so this does not reaccumulate

`core/workbook_backup.py` is now the one place the four scripts take a backup. It keeps
the newest three and reports what it pruned. Git holds the durable history; a `.bak`
covers only the window between the last commit and a botched `--apply`, and three of them
cover that window as well as thirty did.
