> ⛔→✅ **FROZEN 2026-08-24 (branch-freeze: the blind commit is THE COMMIT INTRODUCING THIS
> BANNER, on branch `carcasum-arb-freeze` — local main is latched under a live reconcile
> suite; the branch merges at the quiet window; a committed sha is a provable freeze on any
> branch, same precedent as `carcasum-match-freeze`/`carcasum-rung2-freeze`). Owner directive,
> verbatim: "I think we should challenge carcasum with the arbiter" 2026-08-24. No game on
> band 144000000000 exists at freeze time. NOT LAUNCHED — this is a build-only deliverable;
> the orchestrator fires it with its own monitors, exactly as
> `carcasum_match_prep/LAUNCH_PROCEDURE.md` did for rung 1. `WORKERS.conf::BLIND_COMMIT`
> cannot be stamped with this commit's own sha inside this same commit — a small follow-up
> commit stamps the real sha before any real launch; `run_cells.sh` refuses a real
> (non-dry-run) launch while it reads PENDING.**

> ⚠️ **AMENDED PRE-LAUNCH #1 (2026-08-24, zero games run; amended blind commit = the commit
> introducing this line).** The band claimed above, `144000000000`, collided with an unmerged
> sibling branch's own same-day claim (`d2r2-freeze`'s `measurement/track_d2r2_prep/`) — a
> main-tree-scoped registry check cannot see claims sitting on other unmerged freeze branches.
> **Band substituted: `144000000000` → `147000000000`.** Every band literal below this line is
> the corrected value; the collision finding, the corrected all-branches sweep procedure, and
> why `146000000000` was also skipped (soft-reserved by `d1-rebase-freeze` for its own future
> use, even though not formally claimed) live in `DESIGN.md` §4.1 — not repeated here, same
> "read-rule stays a small diffable target" discipline `carcasum_rung2_prep/READ_RULE.md`
> already established. Nothing about the gates, statistics, or branch table below changes —
> only the band literals in `G-SHARED-DECKS` (§3) and the top-up seed range (§4).

# READ_RULE — Carcasum arbiter-transfer challenge

> **⚠️ BLIND ORDERING.** This file is committed BEFORE the band is claimed, BEFORE game 1, and
> BEFORE any statistic of this cell exists. The branch that fires is taken **VERBATIM**,
> whatever it is. Owner authorization funds the cell and does not name its answer — same
> discipline as `carcasum_match_prep/PREREG.md` §5 and `carcasum_rung2_prep/READ_RULE.md` §0.
>
> Design: [`DESIGN.md`](DESIGN.md). Run id `carcasum_arb_challenge`. Analyzer:
> `scripts/carcasum_match/analyze_arb_challenge.py` (new, built alongside this pair — §7).

---

## §1 — THE STATISTIC, NAMED BEFORE IT EXISTS

```
For each deck d in the shared range that appears, BOTH seats, in BOTH arms:
    margin_OFF(d) = (margin_OFF(d, seat0) + margin_OFF(d, seat1)) / 2
    margin_ON(d)  = (margin_ON(d, seat0)  + margin_ON(d, seat1))  / 2
    D(d)          = margin_ON(d) - margin_OFF(d)

D        = mean(D(d)) over n_common decks
SE(D)    = stdev(D(d)) / sqrt(n_common)         -- decks are the i.i.d. unit, exactly the
                                                    paired-difference construction
                                                    tiearb_widening's b64_cell/b32v64_cell
                                                    already used for M_WIDE - M_NARROW
z_D      = D / SE(D)
```

**Sign convention, load-bearing:** margin is defined champion-minus-Carcasum (r1's own
convention), so `D > 0` means the arbiter's presence made the champion do BETTER against
Carcasum — a positive transfer. `D < 0` means the arbiter made the champion do WORSE — a
negative transfer, itself a real, reportable finding (§4's `N` branch).

**Secondary, per arm (witness, never a branch input):** each arm's own win rate / elo / margin
vs Carcasum, computed independently for ARM-OFF and ARM-ON. ARM-OFF's own number is a
**cross-band** replication of r1 (`b142000000000`, this cell's band is `147000000000`) — any
comparison between the two carries the full CL-068 cross-band humility discount (1.8-2.2x SD
inflation); it is reported for corroboration only, never in place of `D`.

---

## §2 — UNITS AND POWER

Primary unit: **points/game of final-score margin, ARM-ON minus ARM-OFF, deck-paired
across arms.** Elo is a derived display quantity, computed separately per arm, never on `D`
itself (a point-scale statistic does not need an elo conversion to be interpretable, and
`D`'s own elo-equivalent would require an opponent-specific elo-per-point scale this cell does
not itself measure).

**Power, stated before any number (full derivation: `DESIGN.md` §3):**

```
sigma_D, Model A (precedent, deterministic-opponent widening cells)  ~ 17.7-18.1 pts/deck
sigma_D, Model B (conservative, independent-draw assumption)         = 19.54 pts/deck

n_primary = 200 decks (800 games):
    SE_D(A) = 1.25   z(delta=2.5) = 2.00     SE_D(B) = 1.38   z(delta=2.5) = 1.81
n_after_topup = 250 decks (1,000 games):
    SE_D(A) = 1.12   z(delta=2.5) = 2.23     SE_D(B) = 1.24   z(delta=2.5) = 2.02
```

Both models clear 2 sigma comfortably at the TOP of the expected transfer range (delta=4:
z=2.9-3.2 at n=200). Only Model B's own floor needs the reserved top-up to clear 2 sigma at
the BOTTOM of the expected range (delta=2.5). This is named, not resolved further — the
n=200 primary is deliberately powered against Model A, with the top-up as the guard against
Model B being the truer one (`DESIGN.md` §3.2's flagged decision).

**By construction, at this SE regime, a "significant but below the equivalence bar" case
cannot occur:** `SE_D` at n>=200 is always <=1.4 pts/deck under either model, so `z_D >= 2.0`
implies `|D| >= 2*SE_D >= 2.0*1.0 ... ` more precisely `D >= z_D * SE_D >= 2.0 * 1.12 = 2.24`
pts at the tightest SE and `>= 2.0*1.38=2.76` at the loosest — i.e. **any `|z_D|>=2.0` reading
at this n always exceeds the 2.0-pt equivalence bar too**, so `T`/`N` and the equivalence
region `W` are mutually exhaustive with the top-up gap, with no separate "significant-but-tiny"
case to branch on. Verified by the analyzer's own arithmetic at read time, not merely asserted
here (a future re-derivation that disagrees is itself `U-UNREADABLE`, same discipline as
`carcasum_rung2_prep/READ_RULE.md` §1.2's "recomputation is a witness").

---

## §3 — PRECONDITIONS (every gate individually fail-closed; ABSENT is FAIL)

Each gate is read at the manifest top level, then at `config.*`; the analyzer reports which
address resolved (house `G-BAND`/`G-J1` precedent).

| id | proposition | address | fail on |
|---|---|---|---|
| `G-BINARY` | `manifest.carcasum_binary_sha256` equals the pinned build's sha, recorded at freeze time from whichever box the real launch actually uses (re-pin at freeze, not assumed — the r1/rung2 laptop sha `c090847e1befa...` if this cell also runs on the laptop; a DIFFERENT sha is expected and correct if a different box is used, per `PREREG.md` §4's "the binaries differ, as they must" precedent — the gate is INTERNAL CONSISTENCY between the two arms' own binary shas, not equality to a cross-box constant) | `games.jsonl` line 1 of EACH arm -> `manifest.carcasum_binary_sha256`, cross-checked EQUAL between arms | either arm's sha absent, OR the two arms' shas differ from each other |
| `G-RULES` | `manifest.rules_manifest.name == "fixed_v1"` and `manifest.rules_manifest.r9_env_ok == true`, BOTH arms | `games.jsonl` line 1, each arm -> `manifest.rules_manifest.name`, `.r9_env_ok` | anything else, either arm |
| `G-BUDGET` | `manifest.opponent == {kind:"mcts", budget_ms:5000, playouts:null, cp:0.5, reuse_tree:false, node_priors:false, progressive_widening:false, progressive_bias:false, utility:"portion", playout:"random"}` EXACTLY, BOTH arms, byte-identical between arms | `games.jsonl` line 1, each arm -> `manifest.opponent.*` | any field off-spec in either arm, or the two arms' opponent blocks differ from each other |
| `G-CHAMP-OFF` | ARM-OFF ONLY: `manifest.champion_manifest.leaf_hashes.harness_leaf_hash == "a36d2e15a3b3d71d"` (pinned `PROD_LEAF_HASH`) AND `manifest.champion_manifest.cand_tiearb` absent/null | ARM-OFF `games.jsonl` line 1 | mismatch, OR `cand_tiearb` present (means the arbiter leaked ON on the OFF arm) |
| `G-CHAMP-ON` | ARM-ON ONLY: `manifest.champion_manifest.leaf_hashes.harness_leaf_hash == "a36d2e15a3b3d71d"` (same pin — the arbiter does NOT move the leaf hash) AND `manifest.champion_manifest.cand_tiearb == {enabled:true, B:64, J:4, mode:"argmax", salt:"tiearb2-deploy-v1", eps:0.0}` EXACTLY | ARM-ON `games.jsonl` line 1 | leaf mismatch, OR `cand_tiearb` absent/null (arbiter leaked OFF on the ON arm), OR any field of the resolved dict off the pinned spec |
| `G-SINGLEVAR` | the two arms' manifests agree EXACTLY on: `our_git_rev`, `rules_profile`, `opponent` (see `G-BUDGET`), `sims_override`/`k_dets_override` (both null — the champion runs at the YAML budget, not a smoke override), `execution.backend == "rust"` — i.e. the ONLY manifest field that differs between arms is `champion_manifest.cand_tiearb` | cross-manifest diff, `games.jsonl` line 1 of each arm | ANY of the listed fields differs between arms (this is the `track_d2_prep` G-SINGLEVAR lesson, ported: `results.csv d2_rung_compression_U_UNREADABLE...b141e9` — "the two invocations differ in EXACTLY ONE experimental argument" was asserted by prose there and never checked; here it is checked) |
| `G-N` | each arm independently reaches `n_common_decks >= 160` (80% of the n=200 primary target, the house 80%-floor convention) BEFORE the cross-arm intersection in `G-SHARED-DECKS` is taken | analyzer's own per-arm deck-pairing count | either arm under 160 |
| `G-SHARED-DECKS` | every realized `deck_seed` in EITHER arm's archive is a subset of `{147000000000..147000000249}`; the PRIMARY `D` statistic is computed over the INTERSECTION of the two arms' own realized deck sets (a deck missing from either arm cannot be paired across arms and is excluded from `D`, though it may still count toward that arm's own secondary win rate) | analyzer's own deck_seed collection, both arms | any `deck_seed` outside the shared range in either arm; OR the intersection falls below the `G-N` floor even though each arm individually cleared it |
| `G-TIMING` | median realized `opp_driver_ms_per_turn`, pooled over each arm's own real turns, is within +-10% of 5000ms (looser than rung 2's playout-mode +-5%, because TIME-mode is thread-CPU time and can drift under real contention, not a driver-enforced exact playout count — formalizes r1's own informal `LAUNCH_PROCEDURE.md` §3 watch item, "opp_driver_ms_per_turn drifting well above 5000") | recomputed by the analyzer from every `moves[].opp_driver_ms` field, per arm | either arm outside +-10% |

### §3.1 — `D` — void-contaminated (checked FIRST, before any branch below)

Copied verbatim from r1's `AUDIT_PLAN.md` taxonomy and 1%-of-games bar (`SCORE_FINAL`,
`FARM_SCORE_FINAL`, `MEEPLE_LEGALITY`, `MEEPLE_SLOT_UNMAPPED`, `LEGALITY_OURS_EXTRA`,
`HARNESS_ERROR`, `DRIVER_REJECT`, `SEAT_DESYNC`, `COORD_FRAME_MISMATCH`) — the taxonomy is not
redefined by the arbiter's presence or absence (search-time knob, not a rules knob).

**`D` fires** (checked before any other gate or branch, first-match-wins over everything else)
if:

- any `VOID_*` count, OR any REAL-class divergence count, exceeds **1% of games** in EITHER
  arm's own corpus; OR
- either arm fails to reach its own `DONE` sentinel (§ launcher discipline, `WORKERS.conf`); OR
- ANY of `G-BINARY`/`G-RULES`/`G-BUDGET`/`G-CHAMP-OFF`/`G-CHAMP-ON`/`G-SINGLEVAR`/`G-N`/
  `G-SHARED-DECKS`/`G-TIMING` fails.

`D` -> **`U-UNREADABLE`.** No `D` (the statistic) is published. Diagnose, patch (never touching
`vendor/carcasum/**` or `Carcasum/player/**`), re-audit only what changed, re-run only the
affected arm(s) on the SAME band (the band is not spent by a `U-UNREADABLE` outcome unless a
game record actually exists on it — same convention as `BAND_REGISTRY.csv`'s
"RELEASE-IF-NEVER-LAUNCHED" clause precedent).

---

## §4 — BRANCH TABLE (first-match-wins, `D` checked first per §3.1)

> ⚠️ **This table adds ONE branch, `N`, beyond the task brief's literal T/W/U enumeration.**
> The brief named three outcomes (transfer / washout / unreadable). A credible, statistically
> significant NEGATIVE transfer — the arbiter measurably making the champion WORSE against
> Carcasum — is a real, adjudicable finding (the arbiter's internal win being
> "champion-mirror-specific," exactly the risk `DESIGN.md` §0 names) and is not the same thing
> as "no strength number could be produced." Folding it into `U-UNREADABLE` would misrepresent
> a finding as a gate failure. `N` is therefore a fourth branch, checked alongside `T`/`W`,
> flagged here explicitly as a deviation from the literal brief for the orchestrator to
> confirm or override before launch.

| branch | condition | action |
|---|---|---|
| **T — TRANSFER** | `D >= 2.0` pts AND `z_D >= 2.0` | Report: the arbiter's internal gain (`+66 elo` desktop) transfers externally. State `D`, `z_D`, and the implied elo-per-point conversion from THIS cell's own secondary numbers (not r1's, to avoid a cross-band elo scale). This is new evidence for widening the arbiter's authorized use beyond the champion-mirror confirmation it currently rests on. |
| **W — WASHOUT** | `\|D\| <= 2.0` pts AND `\|z_D\| < 2.0` | Report: the arbiter's internal gain does **not** measurably transfer to this external opponent — a real finding, not a null result to bury. The arbiter's win may be champion-mirror-specific (`DESIGN.md` §0's own framing of the risk this cell exists to price). Does not itself argue for de-authorizing the arbiter's DEPLOYED (internal) use — that rests on its own, already-adjudicated evidence — but it bounds how far the arbiter's authorization should be READ, i.e. it is not evidence the arbiter helps against arbitrary opponents. |
| **N — NEGATIVE TRANSFER** *(flagged addition, §4 preamble)* | `D <= -2.0` pts AND `z_D <= -2.0` | Report: the arbiter measurably HURTS against this external opponent. This does not by itself argue for de-authorizing the deployed internal use (different opponent, different question) but is a concrete counter-example to "the arbiter never costs strength" and should be logged as such in `docs/LEVER_INDEX.md` and flagged in any future arbiter-widening discussion. |
| **top-up (once, C-style, r1 precedent)** | `\|z_D\| < 2.0` AND `\|D\| > 2.0` pts (i.e. neither the equivalence region nor a confident read) | Consume the reserved 50-deck top-up (seeds `147000000200..147000000249`), re-read `D`/`z_D`/`SE_D` over the full n=250 under this SAME table. Fired **once**; a second inconclusive read after the top-up falls to `U-UNREADABLE`, not a second top-up (r1's own "one top-up, pre-registered, no second" discipline). |
| **U — UNREADABLE** | `D` (§3.1) fired, OR the top-up was already consumed and the re-read is still inconclusive | No strength number for `D` is published. Both arms' own secondary absolute numbers may still be reported (with the standing R9-on / non-CRN-opponent / cross-band-to-r1 caveats), clearly labeled as not adjudicating the transfer question. |

**Read-rule discipline:** the fired branch **is** the authorization to report it — a fired
trigger gets run and reported, not re-litigated (house convention, every prereg in this
family).

---

## §5 — WHAT THIS CANNOT SHOW

- Whether the arbiter transfers to opponents OTHER than this exact Carcasum config
  (`PortionUtility`/`RandomPlayout`/`Cp=0.5`/5000ms) — a different Carcasum configuration, or a
  wholly different external engine, is a fresh cell.
- Anything about the arbiter's DEPLOYED internal authorization itself — that rests on its own
  already-closed evidence (`governance/PRODUCTION.yaml tiearb_authorized_by`); this cell can
  only ADD context about how far that authorization generalizes, not revoke or re-confirm it.
- Any correction for the discretized nature of the arbiter's firing rate against a genuinely
  different opponent — the firing-RATE itself (how often a tie is resolved by the arbiter at
  all) may differ against Carcasum vs the champion-mirror opponent, and this cell does not
  separately measure or gate on that rate (only the wall-clock projection, `DESIGN.md` §7,
  depends on it, and only as an uncertainty band, not a branch input).
- The R9-off (`walled`) production elo comparison — same standing caveat every Carcasum cell
  carries.

---

## §6 — CLOSE-OUT

Read with the new analyzer (`scripts/carcasum_match/analyze_arb_challenge.py`, §7 of
`DESIGN.md`), not either predecessor's `summarize()`. Apply this file's §4 exactly as written —
the fired branch IS the authorization to report it, not to re-litigate it. Then the six-touch
checklist (`DESIGN.md` §10).
