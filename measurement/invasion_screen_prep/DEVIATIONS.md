# invasion_screen_prep — execution-layer deviations (post-launch)

## IS-D1 — 2026-08-26 ~22:30Z: ident-precheck misaddressed the config block (statistics-blind fix)

**What happened.** CELL IDENT completed healthy (400/400, n_failed=0, D=+0.8325, z=0.9624 —
INSIDE the |z|≤2.0 bar) but the launcher's ident-precheck declared `leaf_hash_is_champion`
FAIL and stopped the round (fail-closed, by design, ~8 core-h spent instead of ~62).

**Root cause.** The precheck read `config` off `summary.json`; this harness's `summary.json`
carries NO config block (the split is documented in `analyze_screen.py`'s module docstring:
config-shaped addresses → `manifest.json`; statistics → `summary.json`). `cfg` came back
`{}` ⇒ `cand_h=None` ⇒ fail-closed. The same empty dict made `leaf_diff_empty` pass
vacuously (`{}=={}`), which is the tell preserved in the driver log.

**Ground truth, verified before the fix.** `ident/manifest.json`: `cand_leaf_hash =
opp_leaf_hash = a36d2e15a3b3d71d` (the champion pin) on both sides; invasion keys absent on
both sides identically. The archive is a valid champion-vs-champion identity cell. The
adjudicator-of-record (`analyze_screen.py`) reads the correct addresses and shares no part
of this defect.

**The fix.** One address change in the precheck heredoc (`manifest.json` for config,
`summary.json` retained for `n_failed`), commented at the site. No bar, no statistic, no
gate-of-record touched — the class is execution-layer/statistics-blind (the everyply
EP-D1..D5 precedent). The IDENT archive is retained as-is; the round resumes with the
precheck re-evaluated over the SAME emitted files.

**Why the smoke could not catch it.** The smoke leg runs a B_MID-shaped cell and never
exercises the ident-precheck path; the precheck's first-ever execution was on the real
IDENT cell. (Instrument-hardening note for future pairs: any launcher-side gate that runs
only once per round needs its own selftest fixture.)

**Committed** after RUN_LIVE cleared, per the freeze-latch discipline.

## IS-D2 — 2026-08-29: bar-library import hardened to round 3's by-path form (statistics-blind)

**What was wrong.** `analyze_screen.py` loaded its bar library as a bare `import screen_lib`
after inserting its own directory on `sys.path`. Rounds 1, 2 and 3 each ship a *different*
`screen_lib.py` (sha256 `6168b325…` / `0824a3e2…` / `47c01830…`), so in any process that
touches two rounds — the instrument suite is exactly that — whichever loaded first won
`sys.modules["screen_lib"]` and the second adjudicator silently read the **wrong round's
bars**. Round 3 shipped with the fix already; rounds 1 and 2 did not.

**The fix.** Copied round 3's pattern verbatim: load `screen_lib.py` **by path** under the
directory-qualified module name `screen_lib__invasion_screen_prep`, registered in
`sys.modules` before `exec_module` (so `@dataclass` can resolve its field annotations). The
`sys.path` insertion is removed. `screen_lib` itself has no local imports, so nothing else
depended on that path entry.

**Why it is statistics-blind.** The same `screen_lib.py`, byte-for-byte, from the same
directory, is what gets loaded — only the *name it is filed under* changes. No bar, gate,
threshold, branch table, statistic or verdict of this round moves; the round is closed and
its verdict stands unaltered.

**Verification.** `--selftest` GREEN (0 sanity problems, all 18 gate ids evaluated, ABSENT-is-FAIL
holds). Cross-round proof: loading all three rounds' adjudicators in one process now gives each
its own `screen_lib` and leaves no bare `screen_lib` in `sys.modules`. Running the three
instrument suites **together** went from **50 failures to 4** — and those 4 are exactly the
failures each suite already produces when run alone (three `BAND_CLAIMED`-sentinel freeze-time
interlocks, which now trip because the bands have since been claimed, plus one pre-existing
round-2 wheel-preflight failure). Nothing this edit touched is among them.
