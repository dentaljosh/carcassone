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
> introducing this line).** Pre-launch review found that the band claimed above,
> `144000000000`, **collided with an unmerged sibling branch's own same-day claim**
> (`d2r2-freeze`'s `measurement/track_d2r2_prep/`, also `144000000000`) — both claims were
> made in good faith against the checked-out repo's own `governance/BAND_REGISTRY.csv`, which
> is **blind to claims committed on OTHER unmerged freeze branches**. This pair's own build had
> already run the "re-verify the registry + census a live run" check **twice** (once at design
> time, once immediately before the CSV append) and still missed it, because both checks were
> scoped to the main-tree checkout, not to every branch. **Band substituted: `144000000000` →
> `147000000000`.** Full finding, the corrected all-branches procedure, and why `146000000000`
> was also skipped: §4.1. Every file where the old band appeared (`BAND_CLAIM.json`,
> `BAND_CLAIMED`, this file, `READ_RULE.md`, `WORKERS.conf`, `scripts/carcasum_match/
> analyze_arb_challenge.py`) is amended in the same commit; `run_cells.sh` carries no
> band literal (it reads `WORKERS.conf`) and needed no edit. `WORKERS.conf::BLIND_COMMIT` is
> re-stamped to this amendment commit's own sha by the same follow-up-commit convention as the
> original freeze. **Nothing about the design, power arithmetic, sequencing, or branch table
> changes — only the band.**

# CARCASUM ARBITER-TRANSFER CHALLENGE — DESIGN

This is the single non-banner status paragraph in this file — deliberately, after
`carcasum_match_prep/PREREG.md`'s own frozen text was found to retain a stale `STATUS: DRAFT`
paragraph beneath its FROZEN banner (flagged in that cell's own r1 READOUT §6 as a documentation
defect). Nothing below contradicts either banner above it. **The orchestrator launches; this
build stops at the smoke (§9).**

Design: this file. Read-out branch table: [`READ_RULE.md`](READ_RULE.md). Constants:
[`WORKERS.conf`](WORKERS.conf). Launcher: [`run_cells.sh`](run_cells.sh). Band claim:
[`BAND_CLAIM.json`](BAND_CLAIM.json).

---

## 0. What this cell is, and what it inherits

Rung 1 ([`measurement/carcasum_match_prep/PREREG.md`](../carcasum_match_prep/PREREG.md))
established Carcasum's `MCTSPlayer<PortionUtility,RandomPlayout>@5000ms/turn` as a usable,
non-saturated external reference: the **unmodified** champion (no tie-arbiter) won by
**+4.08 pts/deck (z +4.18, n=400)**. Rung 2
([`measurement/carcasum_rung2_prep/`](../carcasum_rung2_prep/)) is the budget ladder against
that same unmodified champion. Neither rung has ever run the champion **with** the tie-arbiter
against Carcasum — the arbiter's only confirmed wins to date are **internal**, against the
unmodified champion as opponent (`governance/PRODUCTION.yaml
tiearb_authorized_by`, the b64/b32v64 game cells). This cell asks the question those internal
cells cannot: **does the arbiter's internal gain transfer to an external, out-of-lineage
opponent?**

**Inherited verbatim from r1, not re-derived:** opponent identity/config (`MCTSPlayer<
PortionUtility,RandomPlayout>`, `Cp=0.5`, `reuseTree=false`, no priors/widening/bias,
`budget_ms=5000`, `mIsTimeout=true` — TIME mode, not playout mode, so the pre-7ed24075
`read_timeout_s` formula applies unchanged: `max(30.0, (budget_ms or 5000)/1000*4+15.0) =
35.0s`); rules profile `fixed_v1` + `CARCASSONNE_FIX_R9=1`, both sides; deck-paired
seat-swapped CRN structure; the non-CRN-opponent posture (Carcasum's RNG seed is
compile-time only — decks and seatings are exactly reproducible, the opponent's MCTS search
is not); the divergence-audit gate class and 1%-of-games void bar (r1's `AUDIT_PLAN.md`
taxonomy, PASS 50/50 at the one-time audit, reused without re-running); median-not-mean
discipline for any playouts/turn statistic (moot here — TIME mode has no assigned playout
count); R9-on posture (not comparable to `walled` production elo, same standing caveat every
Carcasum cell carries).

**Inherited from rung 2's amendment #2, adapted:** the fail-closed, manifest-address-named
gate discipline (`G-BINARY`, `G-RULES`, `G-BUDGET`, `G-N`, `G-SHARED-DECKS`) — same shape,
same "ABSENT is FAIL" rule, same requirement that the analyzer report which address resolved.
**One gate is deliberately inverted from every prior Carcasum cell**: `G-CHAMP` here does
**not** assert the arbiter is off. It asserts, per arm, that the arbiter is in the state that
arm is supposed to be in — off for ARM-OFF, armed exactly as `governance/PRODUCTION.yaml
fair_deploy.tiearb` for ARM-ON. Getting this backwards (both arms accidentally reading the
r1/rung2 "tiearb absent" convention) would silently turn ARM-ON into a second ARM-OFF and this
whole cell into a null replicate — so `G-CHAMP` is split into `G-CHAMP-OFF` and `G-CHAMP-ON`
below, each addressed to its own arm's manifest only, and a fifth new gate (`G-SINGLEVAR`)
checks that the two arms' manifests agree on **everything except** the arbiter block — the
exact discipline whose absence sank `track_d2_prep` (`G-SINGLEVAR mixed repo revision between
legs`, `results.csv d2_rung_compression_U_UNREADABLE...b141e9`). This cell was built with that
failure in view.

**What is new:** two arms on one shared fresh deck band; a harness capability that did not
exist before this build (§8); a difference-of-differences estimator; and a branch table shaped
by the owner's brief (§4 below and `READ_RULE.md` §4), not copied verbatim from either
predecessor.

---

## 1. Primary question and estimator

**Primary:** does the root tie-arbiter's internal gain (`governance/PRODUCTION.yaml`, `B=64
J=4 mode=argmax salt=tiearb2-deploy-v1 eps=0.0 threads=8`) transfer to an external opponent?
Measured as the **deck-paired difference of margins**, ARM-ON minus ARM-OFF, both vs the same
Carcasum config, on the **same decks**:

```
D = mean over shared decks of [ margin_ON(deck) - margin_OFF(deck) ]
    margin_X(deck) = (margin_X(deck, seat0) + margin_X(deck, seat1)) / 2   -- per-arm
                      seat-paired margin, champion-minus-Carcasum, points
SE(D), z_D = D / SE(D)                          -- paired SE over the shared-deck sample
```

This is the exact within-pair-CRN construction the `tiearb_widening_20260817` game cells
already used for their `D = M_WIDE - M_NARROW` primary (`results.csv
tiearb_widening_b64_gamecell_...`, `...b32v64_gamecell_...`) — extended here from "both arms
vs the unmodified champion" to "both arms vs Carcasum". **Why this is the right primary, not
each arm's absolute margin separately:** an absolute margin difference across two SEPARATE
Carcasum matches would need the full cross-band humility discount (CLAUDE.md CL-068,
1.8–2.2×); the SAME-band, SAME-deck, SAME-launch-window paired difference does not, because
deck variance cancels the way it always does under deck-pairing, extended one level (pairing
across ARMS, not just seats). **This is the entire reason the two arms share one band and one
deck set** — see §4.

**Secondary (witness, never a branch input):** each arm's own absolute margin/win-rate/elo vs
Carcasum. ARM-OFF is, by construction, a byte-for-byte replication of r1's own configuration on
a **fresh band** — its own absolute number is reportable, but **any comparison to r1's +4.08 is
a cross-band comparison and inherits full CL-068 humility** (1.8–2.2× SD inflation on the
contrast); it may corroborate but never substitutes for the within-pair `D`.

---

## 2. Configuration — both arms, table

| | ARM-OFF | ARM-ON |
|---|---|---|
| **Champion** | the champion of record, `governance/PRODUCTION.yaml` fair deploy: `k8×1376=11008`, rust backend, `verify=True`, curve125 leaf, leaf hash `a36d2e15a3b3d71d`. **No tie-arbiter.** | **Identical**, plus the root tie-arbiter exactly as `fair_deploy.tiearb`: `B=64, J=4, mode=argmax, salt="tiearb2-deploy-v1", eps=0.0, threads=8`. Leaf hash **unchanged** (the arbiter is a search knob, not a leaf field — the champion's manifest carries the SAME `a36d2e15a3b3d71d`). |
| **Opponent** | `MCTSPlayer<Utilities::PortionUtility, Playouts::RandomPlayout>`, `Cp=0.5`, `reuseTree=false`, no priors/widening/bias, `budget_ms=5000, mIsTimeout=true`. **Byte-identical between arms** — this is the r1 config verbatim. | same |
| **Rules** | `fixed_v1` + `CARCASSONNE_FIX_R9=1`, both sides | same |
| **Deck band** | shared 250-seed range `147000000000..147000000249` (§4, amended §4.1) | **the same range** — within-pair CRN |
| **Hardware** | one box, exclusive tenancy (laptop, once free — §7) | same box, same launch window (§6) |

**Single-variable discipline (the `G-SINGLEVAR` gate, §0):** the two arms' launch commands
differ in **exactly six arguments** — the six `--champ-tiearb-*` flags (§8) — and nothing
else: same `--decks`, same `--seed-base`, same `--binary`, same `--opp-*` flags, same
`--rust-threads`, run from the **same commit**. The analyzer verifies this from the manifests
themselves, not from the launch command (a launch-command diff proves intent; a manifest diff
proves what actually ran).

---

## 3. Power arithmetic

**Expected effect if the arbiter transfers:** the desktop internal gain is **+66 elo**
(`b32v64_cell` CELL_B64 vs the common champion-mirror opponent, `margin +5.2123` pts/game
elsewhere in that record, but the **portable** figure — because elo-per-point conversion is
opponent-specific — is the **elo** number, `+66.4644`). Converting to Carcasum's own
elo-per-point scale (r1: `48.08` elo over `4.08` pts ⇒ **16.12 elo/pt**, `results.csv
carcasum_match_r1_...`): `66.4644 / 16.12 ≈ 4.12 pts/deck` **if the internal gain transferred
undiscounted**. It should not be assumed to: the arbiter's tie-break value estimate was tuned
and confirmed against the champion's own mirror-image search, and a genuinely different
opponent (different playout policy, different utility, different search shape) could see a
smaller — or larger, or reversed — effect. **Expected range, discounted for transfer
uncertainty: +2.5 to +4 pts/deck.** This cell sizes to the **bottom** of that range (standard
practice: size for the smallest effect that still matters, not the point estimate).

### 3.1 The SE model, stated before it decides anything

No cell has ever measured `Var(D)` for "arbiter-on minus arbiter-off, both vs a NON-CRN
opponent" — the closest precedents measured `Var(D)` for "B=64 minus B=16/B=32, both vs a
CRN (fully deterministic) opponent," which is a **different** noise regime: with a
deterministic opponent, the ONLY source of arm-to-arm variance is the arbiter's own tie-break
outcome; with Carcasum, each arm's games ALSO carry Carcasum's own non-reproducible search
variance, independently per arm (a tie that changes the champion's move on ARM-ON can cascade
into a completely different Carcasum trajectory thereafter, uncorrelated with what Carcasum did
in the same deck's ARM-OFF game).

Two models, both grounded in real measurements, bracketing the true `σ_D`:

```
σ_paired (r1, ONE arm vs Carcasum, n=200 decks)
    = SE(d) x sqrt(n) = 0.9772 x sqrt(200) = 13.82 pts/deck

MODEL A -- "precedent" (assumes the SAME correlation the deterministic-opponent
           widening cells measured carries over unchanged):
    sigma_D ~= 17.7-18.1 pts/deck
    (tiearb_widening b64_cell: SE_D 0.6463 @ n=750 decks -> sigma_D = 0.6463*sqrt(750) = 17.70
     tiearb_widening b32v64_cell: SE_D 0.4671 @ n=1497 decks -> sigma_D = 0.4671*sqrt(1497) = 18.07)
    Optimistic: assumes Carcasum's added opponent-side noise does not erode the
    arm-to-arm correlation much below what a deterministic opponent already showed.

MODEL B -- "conservative / independence" (treats each arm's game against the
           non-CRN opponent as an independent draw, crediting NO covariance
           from sharing a deck -- the worst case for power):
    sigma_D = sqrt(2) x sigma_paired = sqrt(2) x 13.82 = 19.54 pts/deck
```

The true value is almost certainly between these — decks are shared (some correlation
survives) but the opponent is not deterministic (some correlation is destroyed). **This cell
sizes using Model B** (the more conservative bound), because a false "the arbiter transfers"
verdict from an underpowered cell is a worse failure mode here than a slightly larger n, and
because unlike a budget-ladder rung, there is no cheap follow-up cell already queued to catch
an underpowered read.

### 3.2 n

```
target: SE_D <= delta/2 = 2.5/2 = 1.25 pts/deck, for z >= 2.0 at delta = 2.5 (bottom of
        the expected range)
n_decks >= (sigma_D / 1.25)^2

Model B (conservative): n_decks >= (19.54/1.25)^2 = 244.1
Model A (precedent):    n_decks >= (17.7 /1.25)^2 = 200.5   <- lands almost exactly at n=200
```

**Chosen: n_primary = 200 decks x 2 seats x 2 arms = 800 games.** This is Model A's own
answer, deliberately — it also matches the owner's own back-of-envelope range (150-200 decks)
and lands the wall-clock projection (§7) at ~4h, the stated expectation. It is **not**
Model B's answer; Model B's own floor (244 decks) is not fully cleared by n=200 alone:

```
at n=200:  SE_D(A)=1.252  z(delta=2.5)=2.00   SE_D(B)=1.382  z(delta=2.5)=1.81
at n=250:  SE_D(A)=1.119  z(delta=2.5)=2.23   SE_D(B)=1.236  z(delta=2.5)=2.02
```

So: **reserve a 50-deck top-up (to n=250, matching r1's own "reserve the top-up range up
front" convention) that clears Model B's own 2sigma bar at the bottom of the expected range.**
The top-up is consumed once, only if the primary read is genuinely inconclusive (`READ_RULE.md`
§5) — not automatically, and never twice.

**⚠️ Decision flagged for orchestrator review:** this cell is powered against Model A (the
optimistic bound) at n=200, with a reserved escape hatch to clear Model B (the conservative
bound) at n=250. If the orchestrator wants primary power against the conservative bound
outright, `WORKERS.conf::N_DECKS_PRIMARY` should be set to 250 (not 200) before launch — a
one-line change, no re-design needed, but it changes the wall-clock from ~4.0h to ~5.0h and
was not made unilaterally here because it would have overridden the owner's own stated
expectation without a round-trip.

---

## 4. The band

**Registry state, re-verified fresh at draft time (not assumed from the task brief's own
"likely 146000000000" guess):**

```
$ git -C . log --oneline -1 -- governance/BAND_REGISTRY.csv   # d34521c6, current tip
$ python3 -c "... max(band_seed_start) over all 70 rows ..."
max seed start = 143000000000   (the rung-2 claim, carcasum_rung2_prep, still LIVE)
```

**⚠️ The task brief's "registry high-water 145e9, likely 146000000000" does not match the
registry as re-read.** The actual high-water mark is `143000000000` (rung 2's own claim,
consistent with `STATUS.md`'s own "rung-2 is the one thing still live" note and the git log
above) — nothing has claimed 144e9 or 145e9 **on the checked-out branch**. A live-run process
census (`ps`, `find ... RUN_LIVE.json`) at draft time found no process and no `RUN_LIVE.json`
touching the 144e9-146e9 range either.

> ⚠️ **This was `144000000000` at the original freeze commit (`7cd3aafb`), and `144000000000`
> is now TAKEN — by an unmerged sibling branch, not by anything the main-tree registry check
> above could see.** A pre-launch review (§4.1) found that `d2r2-freeze`'s own
> `measurement/track_d2r2_prep/` had claimed the SAME band, `144000000000`, the SAME day, on
> ITS branch — a genuine race between two independent, good-faith builds, each checking the
> ONE registry file each could see from its own checkout. **The general lesson, worth more
> than the number (same shape as r1's own PREREG.md §3 losing 1.41e11 this way once):** a
> band-freedom check scoped to `git log`/`python3 -c "..."` against the CHECKED-OUT branch's
> `governance/BAND_REGISTRY.csv` is blind to every claim sitting on an unmerged sibling
> branch — and this program currently has SIX such freeze branches alive at once
> (`carcasum-match-freeze`, `carcasum-rung2-freeze`, `carcasum-arb-freeze`, `d1-rebase-freeze`,
> `d2r2-freeze`, plus whatever the next one is). **The corrected procedure, for the next
> claimer:** sweep every local branch, not just the checkout — `for b in $(git for-each-ref
> --format='%(refname:short)' refs/heads/); do git ls-tree -r --name-only "$b" --
> measurement/ | grep -i 'BAND_CLAIM\.json$'; done`, then `git show <branch>:<path>` each hit
> to read its claimed range, THEN take the lowest free integer above the highest thing seen
> anywhere — not just above the local registry's own high-water mark. §4.1 has the full sweep
> this correction is based on.

### 4.1 Band substitution amendment (2026-08-24, zero games run)

**Finding.** The all-branches sweep (the corrected procedure above, run against this repo's
~150 local branches) found band claims sitting on THREE freeze branches invisible to the
main-tree checkout:

| branch | band | status | source |
|---|---|---|---|
| `d2r2-freeze` | `144000000000` | claimed, registry row present on that branch | `measurement/track_d2r2_prep/BAND_CLAIM.json` + that branch's own `governance/BAND_REGISTRY.csv` |
| `d1-rebase-freeze` | `145000000000` | claimed, registry row present on that branch | `measurement/track_d1_fair_rebase/BAND_CLAIM.json` (`_role: PRIMARY`) |
| `d1-rebase-freeze` | `146000000000` | **soft-reserved, NOT in that branch's own registry** (`status: DRAFT-NOT-CLAIMED`) | same file (`_role: RESERVATION -- append ONLY if the owner wants the range held... No cell may run on this range without a fresh owner funding decision`) |

`146000000000` is, by the letter of "no branch claims it," free — `d1-rebase-freeze` never
appended it to any registry and its own status field says `DRAFT-NOT-CLAIMED`. **This design
skips it anyway**, deliberately more conservative than the letter requires: that track has
already spent a paragraph explaining exactly what it wants `146000000000` for (a `n=800`
n-extension of its own six-cell design) and explicitly asked that nothing run there without
its own fresh funding decision. Taking it for an unrelated cell — even one that is, today,
technically unclaimed — would manufacture the identical collision this amendment exists to
fix, the moment that track's own extension gets funded. **Band substituted:
`144000000000` → `147000000000`** — confirmed clear by the same sweep (no branch, anywhere,
mentions `147000000000`) and clear of every registry high-water mark found on any branch
(`145000000000` is the highest ACTUAL claim on any branch; `146000000000` is spoken for in
spirit).

**Amended band block (supersedes the struck block above in every particular):**

```
band_seed_start : 147000000000
label           : CARCASUM ARBITER-TRANSFER CHALLENGE: two deck-paired arms on ONE band,
                  ONE shared 200(+50 topup)-deck set. ARM-OFF = production champion
                  (k8x1376 rust fixed_v1+R9 curve125, NO tie-arbiter) vs Carcasum
                  MCTSPlayer<PortionUtility,RandomPlayout> @5000ms/turn Cp=0.5 --
                  byte-identical to carcasum_match_r1's own config, on a FRESH band.
                  ARM-ON = the SAME champion + PRODUCTION.yaml root tie-arbiter
                  (B=64 J=4 argmax salt=tiearb2-deploy-v1 eps=0.0 threads=8) vs the
                  SAME Carcasum config. PRIMARY = deck-paired D = M_ON - M_OFF.
tier            : claim
status          : (open at commit)
claimed_date    : (date of blind commit)
decision_influenced : (blank until close-out)
evidence_or_claim   : measurement/carcasum_arb_challenge_prep/DESIGN.md -> the committed design
notes           : Seeds 147000000000..147000000199 = 200 decks x 2 seats x 2 arms = 800
                  games PRIMARY. TOP-UP RANGE RESERVED UP FRONT:
                  147000000200..147000000249 (50 more decks, consumed ONLY if
                  READ_RULE.md's top-up branch fires, ONE top-up, no second --
                  matching the 142e9/r1 top-up convention). BOTH ARMS DRAW THE SAME
                  SEED RANGE (within-pair CRN, rung-2's shared-decks convention,
                  READ_RULE.md SS1) -- per-arm separation is by OUTPUT PATH, not seed
                  offset. BAND SUBSTITUTED 2026-08-24 (SS4.1): the original claim,
                  144000000000, collided with an unmerged sibling branch's own
                  same-day claim (d2r2-freeze's track_d2r2_prep) that a main-tree-scoped
                  registry check could not see; 146000000000 was also skipped, not
                  because any branch has formally claimed it, but because
                  d1-rebase-freeze has explicitly earmarked it for its own future
                  n-extension. Zero games ran on 144000000000 before the substitution --
                  no BAND_REGISTRY.csv row for it survives on this branch (this
                  amendment REPLACES that row with the 147e9 row, in the same commit).
```

**Band hygiene.** The G-MODE-class smoke (§9) uses a disjoint dev-tier throwaway seed, never
pooled, never claimed.

---

## 5. Structural gates and the branch table — pointer

Full gate table (`G-BINARY`, `G-RULES`, `G-BUDGET`, `G-CHAMP-OFF`, `G-CHAMP-ON`,
`G-SINGLEVAR`, `G-N`, `G-SHARED-DECKS`, `G-TIMING`), the void-contaminated `D` check, and the
branch table (`T`-transfer / `W`-washout / `N`-negative-transfer / one top-up / `U`-unreadable,
first-match-wins, `D` checked first) all live in [`READ_RULE.md`](READ_RULE.md), matching the
`DESIGN.md`/`READ_RULE.md` split rung 2 established.

⚠️ **`READ_RULE.md` adds one branch beyond the brief's literal T/W/U enumeration** — `N`, a
credible **negative** transfer (the arbiter measurably *hurts* against Carcasum) — flagged
explicitly in that file as a deviation, with the reasoning: lumping a real, statistically
adjudicable negative result into "unreadable" would misrepresent a finding as a gate failure,
which this program's own discipline treats as a category error (`U-UNREADABLE` is reserved for
"no strength number was produced," not "a strength number was produced and it was bad news").

---

## 6. Sequencing — CONCURRENT/INTERLEAVED, not sequential

**Chosen: both arms launch simultaneously**, each on half the box's workers (`W=7` of the
laptop's `W=14`), running for the same wall-clock window, rather than ARM-OFF-then-ARM-ON (or
the reverse) at full `W=14` each.

**Why, explicitly (the rung-2 thermal/drift lesson this brief points at):** a sequential design
puts the two arms in *different* calendar time — different ambient temperature, different
background load, different point in whatever slow drift the box exhibits over a multi-hour run
(WSL clock drift, thermal throttling, a co-tenant appearing). Any such drift becomes
**indistinguishable from the arbiter's own effect** in a sequential design, because "arm" and
"time" are perfectly confounded. Concurrent execution puts both arms in the **same** calendar
window for their **entire** duration — any drift affects both arms identically and cancels in
the paired difference `D`, exactly the way deck-pairing already cancels deck-to-deck variance.
This is strictly stronger than "alternating blocks" (which still separates the two arms in time
within each block) and costs **nothing**: total core-seconds needed is fixed by the game count,
so `W=7 + W=7` running concurrently for time `t` uses the same total core-time as `W=14` running
each arm sequentially for `t` each — the wall-clock total is identical (§7), the drift
protection is not.

**Implementation:** `run_cells.sh` backgrounds both arms' `match.py` invocations (`&`), each
pointed at its own `--out` subdir and log, then `wait`s on both. Each arm still gets its own
abort-to-partial timeout, its own void-rate circuit breaker (§8.2), and its own `DONE`/`FAILED`
sentinel — concurrency changes only *when* the two run, not their independence as archives.

---

## 7. Wall-clock projection

**Basis:** r1's own realized **249.7 s/game mean** (`results.csv`, `PREREG.md` §2.1/§4.3),
carried forward unmodified for the opponent-side cost (Carcasum's config is byte-identical
between arms and to r1) and for ARM-OFF's champion-side cost (byte-identical champion to r1).

```
PRIMARY: 800 games total (200 decks x 2 seats x 2 arms)
  total core-seconds ~= 800 x 249.7s = 199,760 core-s
  at W=14 total (split 7+7 concurrent, OR 14 sequential-per-arm -- same total):
    199,760 / 14 = 14,269 s = 3.96 h  ~4.0h        <-- matches the task brief's own
                                                        "600-800 games ~ 3-4h" almost exactly

WITH TOP-UP (if the top-up branch fires): +200 games (50 decks x 2 seats x 2 arms)
  1,000 games total -> 199,760 + 49,940 = 249,700 core-s / 14 = 17,835 s = 4.95 h ~5.0h
```

**⚠️ One-sided uncertainty, named:** ARM-ON's champion-side cost is **not** byte-identical to
r1/ARM-OFF — the arbiter adds cost on every ply where it fires (a resolved exact tie on a TILE
placement), at roughly 3.5-6.8x the per-ply baseline depending on the threading knob
(`PRODUCTION.yaml`: "~3.5x per move sequential... fires on tied plies only" at threads=1; the
threads=8 knob is a **latency-only** lever that does not change which plies fire or the games
played, only how fast the fired plies resolve — `PRODUCTION.yaml`'s own gate: "BIT-IDENTICAL by
gate... NO strength claim owed"). Tied plies are a minority of a game's plies, so the total
inflation is expected to be modest, but this cell has **no measured firing rate against
Carcasum specifically** (only against the champion-mirror opponent in the widening cells) — the
projection above should be read as a **floor**, not a guarantee. **Validate, don't trust**
(the house discipline every launch doc in this family repeats): re-project off the first ~20
games of EACH arm before assuming the total, exactly as `carcasum_match_prep/LAUNCH_PROCEDURE.md`
§3 does.

---

## 8. Harness change — `scripts/carcasum_match/match.py` gains tie-arbiter plumbing

**This did not exist before this build.** `match.py::_make_champion` called
`make_production_champion("fair", ...)` with **no `tiearb` keyword at all** — there was no way
to arm the arbiter through this harness, at all, for either arm. `make_production_champion`
itself has carried a `tiearb: dict | None = None` kwarg since the arbiter's factory-level
wiring (`src/carcassonne_ai/champion_factory.py`), and **two sibling out-of-lineage-match
harnesses already expose it**: `scripts/jcz_match/match.py` (`--champ-tiearb-enabled/-b/-j/
-mode/-salt/-eps`, `_resolve_tiearb`, `_champ_tiearb_telemetry`, `manifest["champion_manifest"]
["cand_tiearb"]`) and `scripts/human_anchor/play_harness.py` (`--tiearb-*`, the same shape).
**This build ports the `jcz_match/match.py` pattern into `carcasum_match/match.py` field-for-
field** (same flag names prefixed `--champ-tiearb-*`, matching the sibling harness's own
"our side is the champ" naming convention, not `play_harness.py`'s bare `--tiearb-*`, so a
reader who knows one out-of-lineage-match harness recognizes the other immediately):

- `_resolve_tiearb(args) -> dict | None` — ported verbatim in shape.
- `_champ_tiearb_telemetry(champ, tiearb) -> dict | None` — ported verbatim in shape; raises
  if an armed game's champion has no `FairAgentRs` (an armed-but-inert config is refused, not
  silently downgraded to a null cell — the exact J13 failure mode `champion_factory.py`'s own
  docstring names).
- `play_one_match(..., tiearb: dict | None = None)` threads `tiearb` through to
  `_make_champion` → `make_production_champion(..., tiearb=tiearb)`.
- `build_manifest`'s `champ_manifest` (i.e. `agent.manifest`, already attached by
  `make_production_champion`) already carries `cand_tiearb` when armed — **no change needed**
  in `build_manifest` itself, only in what gets passed to construct the champion.
- The per-game record gains a `champ_tiearb` key **only on an armed game** (unarmed records are
  byte-identical to every prior Carcasum archive's schema — no key added, no `null` written).
- Six new CLI flags in `main()`'s `argparse` block, defaults matching `jcz_match/match.py`'s
  own except where `PRODUCTION.yaml` differs: `--champ-tiearb-enabled` (off by default —
  **explicit arming required**, same discipline `play_harness.py`'s own comment states:
  *"The harness flag default is still `--tiearb-b 16`, so `--tiearb-b 64` is REQUIRED"*),
  `--champ-tiearb-b` (default 16, **the ARM-ON launch command passes 64 explicitly**),
  `--champ-tiearb-j` (default 4, matches production, passed anyway for the record),
  `--champ-tiearb-mode` (default `argmax`, matches production), `--champ-tiearb-salt` (default
  `"tiearb2-deploy-v1"`, matches production), `--champ-tiearb-eps` (default `0.0`, matches
  production).

**`tiearb_threads=8` is a separate, latency-only rust kwarg** (`rust/carc/carc-py/src/lib.rs`,
`SearchConfig::tiearb_threads`, default 1) — **not** part of the `tiearb` dict `_resolve_tiearb`
builds, by `PRODUCTION.yaml`'s own design (deliberately excluded from the strength-bearing
`cand_tiearb` manifest shape). Whether `make_production_champion`'s current signature exposes a
path to set it is **unverified as of this design** — the build step must grep for a live wiring
path (`champion_factory.py`, `production_prior_cfg`, `HeuristicPriorConfig`) and either wire a
seventh `--champ-tiearb-threads` flag (default 1, ARM-ON launch passes 8) or, if no such path
exists yet, **fall back to threads=1 explicitly and document it** — per `PRODUCTION.yaml`'s
own gate, this changes **only** wall-clock, not the games played, so a threads=1 fallback does
not compromise §1's strength question, only §7's wall-clock projection (which would then run
longer than stated, proportionally to the arbiter's own sequential-vs-8-thread ratio). **Flagged
for orchestrator review either way.**

**Test coverage required before freeze:** a `tests/test_carcasum_match_tiearb.py`
mirroring `tests/test_play_harness_tiearb.py`'s contract shape — armed vs unarmed manifest
byte-identity off the arbiter block, `_resolve_tiearb`'s off-by-default behavior, and
`_champ_tiearb_telemetry`'s raise-on-armed-but-inert guard — plus the existing
`tests/test_carcasum_match.py` suite staying green (22/22 per the `7ed24075` commit message).

---

## 9. SMOKE — required before freeze, zero band cost

Same discipline as rung 2's `DESIGN.md` §8: prove the new plumbing works end-to-end through the
REAL `carcasum_driver` binary (not the stub) before freezing, on a dev-tier throwaway seed,
never pooled. Minimum bar: **2 games with `--champ-tiearb-enabled --champ-tiearb-b 4`** (a
cheap B, not the real 64, purely to exercise the code path fast) against the real binary,
`void=None` both, `replay_ok=True` both, and the archived record's `champ_tiearb` block present
with `fires >= 0` (need not actually fire — a tie is not guaranteed in 2 games — but the
telemetry key must be well-formed). If `--champ-tiearb-threads` was wired (§8), smoke it at
both `threads=1` and `threads=8` and assert **byte-identical** game outcomes (the same
whole-game-invariance property `rust/carc/carc-core/src/fair/mod.rs`'s own test already proves
at the rust layer — this smoke proves it survives the python harness plumbing too).

---

## 10. Close-out obligations

The six-touch checklist in full: `experiments/results.csv` row → `DECISIONS.md` index line →
status banner on this doc + `READ_RULE.md` → governance row flip (`BAND_REGISTRY.csv`,
`CLAIM_REGISTRY.csv` if a claim is minted) → `STATUS.md` top block → roadmap line in
`docs/PROGRAM_ROADMAP_2026-07-07.md`. Then `python3 scripts/doc_lint.py`. Plus, regardless of
outcome, a `docs/LEVER_INDEX.md` row for *"Carcasum arbiter-transfer challenge"*.
