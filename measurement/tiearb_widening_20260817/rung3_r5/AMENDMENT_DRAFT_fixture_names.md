# AMENDMENT — `rung3_r5` fixture-name conflict, resolved (canonical: `READOUT_R5.fixture.json`)

> **⚠️ DRAFT — ORCHESTRATOR REVIEW. STATUS 2026-08-23 — NOT ADOPTED, NOT RULED, NOT ENACTED.**
> This document is a **draft** prereg amendment text for the owner/orchestrator to review and,
> if accepted, promote to DECISIONS.md. Until that promotion it has **no force**: it does not
> amend [`DESIGN.md`](DESIGN.md) or [`READ_RULE.md`](READ_RULE.md), it does not change what
> [`verdicts/READOUT_R5.md`](verdicts/READOUT_R5.md) / `READOUT_R5.json` say, and it changes
> nothing on disk. Nothing here is committed as a ruling — it is text proposed for one.
>
> **The run this amendment concerns is SPENT.** `rung3_r5` ran, scored, and read out on
> 2026-08-20 (branch `X-INCONCLUSIVE`, DECISIONS 2026-08-20); its `READ_RULE.md` carries its own
> banner: *"RAN, SCORED, AND READ OUT... THE READ-RULE IS SPENT. NOTHING FURTHER IS QUEUED ON
> THIS PAIR."* So this is **not** a change of plan for a live or future run — it is a dated,
> documented resolution of a naming conflict that the spent run's own analyzer disclosed but,
> by its own stated policy, declined to resolve.

## 1. The conflict, exactly as it stands in the source documents

Two documents that together govern `rung3_r5` name the same artifact differently:

- **The DESIGN's committed fixture list** — [`DESIGN.md`](DESIGN.md) §"A1's committed fixture
  set" (line 820) — names:
  ```
  fixtures/READOUT.fixture.json        <- widening.*
  ```
- **The DESIGN's own execution-layer ruling**, §"EXECUTION-LAYER COMPLETION — RULED
  (2026-08-19)" (line 313 ff.), item **1. EMISSION TARGET** (line 320–322) — names:
  ```
  A1 fixture `fixtures/READOUT_R5.fixture.json`
  ```

Both clauses are in the **same file**, both post-date each other's section (the fixture-list
table sits earlier in the document than the ruling that names the conflicting file), and
neither was edited to agree with the other before the pair went blind. `DESIGN.md` line 37
already flags this in its own front matter: *"`READOUT.fixture.json` / `READOUT_R5.fixture.json`
naming conflict is disclosed, not resolved."* STATUS.md's parked-item list (item 2, added after
the 2026-08-20 close-out) restates it in the same terms and is explicit that resolving it
**is a prereg amendment, not an analyzer decision** — which is what this document is.

## 2. What the run actually emitted on disk (verified, not assumed)

Checked directly against the live directory and the run's own artifacts, not inferred from
either source document:

- `fixtures/` contains **`READOUT.fixture.json`** (261 bytes, timestamped 2026-08-19 17:34).
  **`READOUT_R5.fixture.json` does not exist anywhere in the run directory** — confirmed by a
  direct `ls` against `fixtures/READOUT_R5.fixture.json` (`No such file or directory`).
- The acceptance harness's own audit record agrees. Both `ACCEPT_A2.json` and `ACCEPT_A3.json`
  carry a `readout_fixture_ambiguity` block:
  ```
  "design_fixture_list_names": "fixtures/READOUT.fixture.json",
  "execution_layer_ruling_names": "fixtures/READOUT_R5.fixture.json",
  "found": "READOUT.fixture.json",
  "handling": "EITHER name is accepted, READOUT_R5 preferred. The pair contradicts itself
               here; this tool REPORTS the conflict and does not edit the pair to settle it."
  ```
  `ACCEPT_A3.json` additionally records `"pass": "A3"`, `"passed": true`, `"n_unresolved": 0` —
  the conflict did not block acceptance; it was disclosed and passed through.
- The read-out itself, `verdicts/READOUT_R5.json`, carries the same block under
  `provenance.fixture`: `preferred: "READOUT_R5.fixture.json"`, `preferred_exists: false`,
  `accepted_alternative: "READOUT.fixture.json"`, `accepted_alternative_exists: true`. (Its
  `name_used` field reflects the analyzer's `--emit-fixture` **write** target, i.e. what it
  would name a freshly-emitted A1 fixture, not which file was read for verification — the file
  that was actually found and read is `READOUT.fixture.json`, per the two lines above.)
- The analyzer's source, `scripts/tiletie/analyze_rung3_r5.py` (lines 158–168), and the
  acceptance harness's source, `scripts/tiletie/acceptance_r5.py` (lines 344–349, 812–816),
  both hard-code the same disclosed, non-resolving policy: prefer `READOUT_R5.fixture.json`,
  accept `READOUT.fixture.json`, record which one was found, and do not edit the DESIGN/RULING
  pair to settle it themselves.

**Conclusion:** the run, as actually executed, used and shipped `READOUT.fixture.json` — the
DESIGN's original name, not the execution-layer ruling's name — under the accept-both policy
that both the DESIGN's ruling and the tooling already state. All 19 read-rule gate rows PASS
and the A3 acceptance pass is clean (`n_unresolved: 0`); nothing about the conflict caused an
unresolved address, a failed gate, or a missing artifact.

## 3. The resolution (proposed ruling)

**Canonical name, going forward: `READOUT_R5.fixture.json`.** This ties the fixture's name to
the run it belongs to (matching every other `_R5`-suffixed artifact in the directory —
`CORPUS_R5.json`, `ARMS_R5.json`, `SMOKE_R5.json`, `STAGING_R5.json`, `RUN_MANIFEST_R5.json`,
`GATE_DISJOINT_R5.json`, and `READOUT_R5.json`/`.md` itself) and matches the name the
execution-layer ruling already gave it and the name the analyzer already prefers.

**The accept-both-and-record behaviour is RATIFIED, not overridden, for the spent run.** For
`rung3_r5` specifically, since the run is spent and already read out, the resolution is
**retrospective and does not touch execution**:

- The DESIGN's fixture-list table (line 820) is corrected, in place, to read
  `fixtures/READOUT_R5.fixture.json` — text-only, matching what its own §"EXECUTION-LAYER
  COMPLETION" ruling already said three sections earlier in the same file.
- The physical fixture on disk, `fixtures/READOUT.fixture.json`, is **not renamed and not
  deleted** by this amendment. It is the artifact the spent run actually verified against, it
  is what `ACCEPT_A2.json`/`ACCEPT_A3.json` audited, and altering a spent run's artifacts after
  the fact is exactly the failure mode a fixture-name amendment must not become. A future
  successor run (only if one is funded — see §4) that wants a bit-identical fixture file named
  `READOUT_R5.fixture.json` should emit a fresh one via `analyze_rung3_r5.py --emit-fixture`,
  which already writes to the preferred name by default.
- The accept-both, prefer-`READOUT_R5`, record-which-was-used policy already implemented in
  `analyze_rung3_r5.py` and `acceptance_r5.py` is **the correct standing behaviour** and this
  amendment does not ask for it to be removed — a tool that fails closed on a naming
  disagreement between two prereg documents, rather than silently picking one, is the
  discipline this campaign has repeatedly needed (see D5.3, the freeze-violation precedent
  logged against this same run). What this amendment supplies is the missing piece: **the
  actual prereg-level decision** on which name is correct, so a future run under a similar
  pair does not have to re-disclose the same ambiguity from scratch.

## 4. Why this is a documented resolution of a spent run, not a plan change

- `rung3_r5`'s `READ_RULE.md` is **spent**: banner reads *"RAN, SCORED, AND READ OUT... THE
  READ-RULE IS SPENT. NOTHING FURTHER IS QUEUED ON THIS PAIR."* Nothing in this document
  reopens it, re-scores it, or re-reads it.
  - `results.csv` row `tiearb_widening_r5_S2_rung3_Jgt4_offline_n1059plies_b135e9_137e9`,
  - the read-out of record `verdicts/READOUT_R5.md` + `READOUT_R5.json` (rev R5.1),
  - the branch fired, `X-INCONCLUSIVE`,
  - and DECISIONS.md's 2026-08-20 entry
  all stand exactly as written. Nothing above is amended by this document.
- No number changes. `Δ_ora`, `R_ora`, every gate verdict, the completion count, and the
  re-open bar (~4× `n`) are all untouched — none of them cite the fixture's filename as an
  input.
- The conflict was **found and disclosed by the run's own instrumentation while it ran**
  (`ACCEPT_A2`/`A3`, both dated within the run's execution window), not discovered afterward by
  a reader. What is new here is only the **naming decision** the DESIGN's own ruling asked for
  and the analyzer's own comment block says explicitly is *"a prereg amendment, not an analyzer
  decision"* (`analyze_rung3_r5.py` lines 158–169; `acceptance_r5.py` lines 344–349).
  This document is that amendment, written after the fact because the conflict was carried
  as a disclosed-not-resolved parked item (STATUS.md parked-item 2) rather than amended
  before the run went blind.

## 5. What this amendment explicitly does NOT do

- Does **not** re-analyze, re-score, or re-read `rung3_r5`. `X-INCONCLUSIVE` stands.
- Does **not** touch `verdicts/READOUT_R5.md`, `READOUT_R5.json`, or either `.invalid-superseded-*`
  sibling.
- Does **not** rename or delete any file on disk. `fixtures/READOUT.fixture.json` stays exactly
  where it is.
- Does **not** flip any row in `governance/CLAIM_REGISTRY.csv` — no claim exists for
  `rung3_r5` to flip (`X-INCONCLUSIVE` minted none, same instrument precedent as rung 2's
  `W-RISING`; confirmed by grep: no `CLAIM_REGISTRY.csv` row references `rung3_r5` or
  `tiearb_widening_r5`).
- Does **not** touch `governance/PRODUCTION.yaml`, `governance/CHECKPOINT_LINEAGE.csv`, or any
  other governance file.
- Does **not** touch `results.csv`, `STATUS.md`, `DECISIONS.md`, `CAMPAIGN.md`, or the roadmap.
  (If accepted, promoting this text is a separate, later act — a DECISIONS.md line and a
  STATUS.md parked-item strike-through — not part of this draft.)
- Does **not** move, weaken, or reinterpret any gate, branch condition, or statistic —
  `Δ_ora`, `R_ora`, the separability blind spot, the power print, or the re-open bar.
- Does **not** license anything. No claim minted, no on-device deploy, no change to the
  deployed B=16/J=4 shape, no license to widen J — all already true of the spent run and
  unaffected by a fixture's filename.
- Does **not** commit to funding, designing, or naming any successor to `rung3_r5`. The
  re-open bar (~4× n) stands as the only path back to this question, per DECISIONS 2026-08-20.

## 6. Adoption path (if the owner accepts this text)

1. Owner reviews and either accepts, edits, or rejects the ruling in §3.
2. On acceptance: a **single-line text correction** to `DESIGN.md` line 820
   (`fixtures/READOUT.fixture.json` → `fixtures/READOUT_R5.fixture.json`, with a footnote citing
   this amendment and the date), recorded in DECISIONS.md as a dated entry citing this file.
3. STATUS.md's parked-item list (item 2, the fixture-name conflict) is struck through and
   annotated "resolved, see `rung3_r5/AMENDMENT_DRAFT_fixture_names.md`" — or renamed off
   `_DRAFT` once adopted, at the owner's preference.
4. No band is claimed, no game is played, no re-scoring occurs, and no other file changes.

---

*Written 2026-08-23. Sources read: [`DESIGN.md`](DESIGN.md) (lines 37, 313–322, 814–823),
[`READ_RULE.md`](READ_RULE.md), `ACCEPT_A2.json`, `ACCEPT_A3.json`,
[`verdicts/READOUT_R5.json`](verdicts/READOUT_R5.json),
[`verdicts/READOUT_R5.md`](verdicts/READOUT_R5.md), `scripts/tiletie/analyze_rung3_r5.py`,
`scripts/tiletie/acceptance_r5.py`, `STATUS.md` (parked-item 2), DECISIONS.md (2026-08-20
entry). Structure matches the campaign's standing amendment precedents:
`measurement/jrules_on_search_20260813/AMENDMENT_1_N4_DIRECTION.md`,
`measurement/opencity_round2_20260814/AMENDMENT_1_C_VOID_AND_RERUN.md`, and the in-DESIGN
`PROPOSED AMENDMENT` convention at `measurement/tiearb_widening_20260817/shared_run/DESIGN.md`
§11.*
