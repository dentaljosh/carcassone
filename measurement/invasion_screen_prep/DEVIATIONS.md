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
