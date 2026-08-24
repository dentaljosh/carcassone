# Every-ply SIZE-1 — execution-layer deviation log (draft for the readout)

BLIND_COMMIT unchanged throughout: c946eae7 (DESIGN.md + READ_RULE.md, FROZEN
banner). All deviations below are launcher/builder execution-layer, made
STATISTICS-BLIND (zero legs had run at each fix), each a numbered follow-up
commit on branch everyply-freeze. Orchestrator-authorized under the standing
statistics-blind instrument-fix doctrine (the same path 9ab8be07 itself rode).

- **EP-D1 (pre-launch, 9ab8be07):** `--arm-builder leaf_topk` routed into
  stage_corpus argv per the pair's own §3.1 fallback ruling (pooled-Q
  unreachable on rust backend — rust stats() exposes N not W).
- **EP-D2 (49ee9183):** stage_pilot() missed the same argv fix (9ab8be07's
  message named only the corpus stage). Pilot fail-closed at builder preflight;
  0/20 coverage; DESIGN §12 ABORT. Fix = argv parity + rc fail-close parity
  with sibling stages (stage_pilot previously printed "PILOT DONE" and touched
  DONE_pilot regardless of rc — false-success sentinel). First failed pilot
  archived at failed_pilot_20260823_rev9ab8be07/.
- **EP-D3 (cd9cfd79):** check_arm_builder_backend() in build_everyply_corpus.py
  read attributes off the resolve_execution() Execution object that don't
  exist (Execution is a dict subclass; only .backend/.is_rust are properties —
  ex.rust_threads / ex.source raised AttributeError). LATENT: the leaf_topk
  path was unreachable before EP-D2. The unit test that "covered" it mocked
  Execution with a plain-attribute class, which is exactly why it shipped —
  fix bundles the real-Execution test. 2-line code diff; full
  test_everyply_readout.py 118/118 pass. Second failed pilot log archived at
  failed_pilot_20260823_rev49ee9183/.

Post-fix: pilot corpus built 20/20 (0 dropped, 0 error) — first clean corpus
pass in the probe's history; pilot completed with the (now fail-closed-honest)
DONE_pilot sentinel. PILOT GATE: **PASS** — 60/60 records ok, crn_verified
60/60, checksum 60/60, coverage 20/20, realized c_ARB 0.242 s/playout vs
committed 0.178 (~1.36×, H estimate 1.0/1.4/1.8h stands, well under the 3.0h
abort-to-partial threshold).

- **EP-D4 (f77aaa66):** full launch refused at G-KNOWNGOOD —
  probe_pickers.py:140 hardcodes DEFAULT_IF_RECORDS on the LOCAL share path
  and gate_knowngood() passed no --if-records (laptop share = /mnt/carc-shared,
  data present). Zero legs ran. Fix = gate_knowngood() threads --if-records +
  --arb-records×3 from the launcher's EXISTING role-resolved $SHARE var (no new
  mechanism). One-pass audit of all 7 box-specific-path sites across the
  launcher + invoked scripts: 2 live (both fixed), 5 dead-from-launcher (left
  untouched, dispositions in the fix agent's report). Smoke: knowngood
  reproduced the published arb F bit-exact (0.2064592832, Δ 0.0e0) locally AND
  on the real laptop run.

LAUNCH OF RECORD (attempt 4, rev f77aaa66): 2026-08-23 ~16:0x, --stage all
--chunks 4, detached, W=16 (3 rust legs 6+5+5, ~99.9% CPU), G-KNOWNGOOD PASS,
corpus chunk1 done → arb pricing reached for the first time. ETA ~1.4h,
abort-to-partial 3.0h.

- **EP-D5 (sha TBD, in flight):** first adjudication returned U-UNREADABLE —
  G-KNOWNGOOD failed at the ANALYZE stage: analyze_everyply.py internally
  re-invokes probe_pickers knowngood at a SECOND call site EP-D4 didn't cover,
  same hardcoded-local-share-path class (spurious refusal on the laptop; 10/11
  gates PASS; records intact). Fix by a FRESH statistics-blind agent (first
  adjudicator + orchestrator disqualified — saw the quarantined statistics),
  aligned to the frozen READ_RULE's documented gate address; re-analyze runs
  LOCALLY on the banked share records into a new out-dir; fresh adjudicator
  re-reads. First adjudication draft: SIZE1_READOUT_DRAFT.md (quarantined
  numbers included there with byte-level independent-recompute agreement —
  they enter the record ONLY via the post-EP-D5 adjudication).

## Close-out drafts (six-touch, quiet window)
- results.csv row: everyply_size1_probe · 2026-08-23 · kill-screen, corpus
  n=450 non-tied plies (307 priced/143 zero-filled, 311 roots), replays band
  28e9 (no new band) · κ̂ +0.0135 se 0.1105 z +0.122 UB95 +0.2346 pts/ply ·
  verdict E-UNRESOLVED (READ_RULE §4 row 5; E-FUND unreachable at SIZE-1 by
  §0.A) · note: powering this κ̂ at 2σ needs ~120,317 positions ≈ 134× max
  constructible supply — lever unmeasurable at feasible scale · record:
  SIZE1_READOUT_FINAL.md (commit with the pair merge).
- DECISIONS entry: every-ply SIZE-1 kill-screen E-UNRESOLVED + the
  unmeasurability arithmetic + EP-D1..D5 chain (5 execution-layer fixes, all
  statistics-blind, frozen pair byte-identical throughout — the branch-freeze
  + blind-fix doctrine's first full workout) + owner park decision (pending).
- LEVER_INDEX row update: ✅ DONE 2026-08-23 evening — edited in place with the
  owner's park ruling ("recommend park-with-annotation - okay"), verdict,
  unmeasurability fact, and mechanism-not-n reopen bar. Commit rides the quiet
  window (bundled with the star-row edit).
- Roadmap: same one-liner; remove the SIZE-2/3 contingency lines (never
  licensed).
- Governance: no band row owed (replays 28e9); CLAIM_REGISTRY row optional —
  if added, claim = the UB95 bound, not the point estimate.

Ops trap recorded: run_probe_DRAFT.sh is tracked mode 644 by design (orchestrator
chmod +x = the launch authorization act) — every bundle-sync RESETS the exec
bit, and nohup of a non-executable file dies silently with an empty log. The
chmod must be re-applied after every sync.

Separate pre-existing bug flagged NOT fixed (outside scope, add to parked
fixes): test_launcher_dry_run_reaches_the_analyze_stage shells out to
run_probe_DRAFT.sh whose internal default REPO is the hardcoded main-tree path,
so the test pollutes the LIVE tree when run from a worktree and its cleanup
checks the wrong path. 19 inert dry-run logs it dropped in the local tree are
quarantined at measurement/everyply_probe_20260823/logs/
DRYRUN_TEST_DROPPINGS_20260823/ (delete at quiet window).

Pattern note for the readout: EP-D2's rc fail-close is what made EP-D3 loud
instead of a silent false success — the guard-parity fix paid for itself on the
very next run.

Adjudication requirement: the eventual READOUT must list EP-D1..D3 with shas,
assert statistics-blindness for each (no leg data existed at fix time — the
archived failed-pilot dirs are the witness), and confirm BLIND_COMMIT bytes
(DESIGN/READ_RULE) identical from c946eae7 through the run rev
(`git diff c946eae7..<run-rev> -- DESIGN.md READ_RULE.md` must be empty).
