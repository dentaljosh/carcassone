# FPU PRODUCTION-H2H **ROUND 2** — PRICING THE DEPLOYED CONFIGURATION AT DOUBLE `n` — READ RULE

> **STATUS: FROZEN** (2026-09-01). This document and [`DESIGN.md`](DESIGN.md) are **the pair**, and
> the pair is law. ⛔ **NOTHING IN THIS FILE MOVES AFTER THE BLIND COMMIT.** Every bar, every gate,
> every branch and every prohibition below exists **before any game does**.
>
> If `analyze_h2h.py`, `screen_lib.py` or `run_cells.sh` disagrees with this document,
> **it is the code that is wrong.**
>
> ⚠️ **After game 1 there is no amendment route.** The only one that exists is: freeze the verdict as
> it stands, record the defect, and get the **OWNER** to authorise a re-read of the SAME archive under
> a named, minimal, single-clause correction.
>
> ⛔ **0 games have been played at this commit. No band is claimed at this commit.**
> `analyze_h2h.py --selftest` is `PASS`. ⭐ **Both boxes' `W` are stamped** (`W_LAPTOP = 26`,
> `W_LOCAL = 30`, both measured arb-on at this round's exact cell shape); ⛔ `run_cells.sh` still
> refuses any box whose `W` reads `TBD_FROM_SWEEP`, in every mode. ⚠️ `W` is throughput-only and
> resolves no bar.

**ONE cell:** `CELL_H2H2_FPU02` — `fpu_reduction = 0.2` on the **candidate only**, band
`169000000000`, **`n=1600` deck-paired (800 seat-balanced decks × 2 seatings)** against the
**DEPLOYED CHAMPION**: fair PIMC `k16 × 1376 = 22016` **and the deployed root tie arbiter
`B=64 / J=4 / argmax / salt tiearb2-deploy-v1 / eps 0.0 / phase_gate all`**, ⭐⭐ **ARMED ON BOTH
SEATS**. Executed as **8 chunks of 100 decks** that tile the band, on **one or two boxes** (§6).

⚠️ `W` and the **box assignment** are **throughput-only**. Games are bit-identical at any `W`, and
**no gate in this pair reads a clock or reads which box played what as anything but provenance**.

---

## 0. ⭐⭐ WHAT THIS ROUND IS, AND WHAT IT IS NOT

**ROUND 1** (band `168e9`, `n=400` decks, same arms, same bar) read **`H-UNRESOLVED`**:
`M = +1.019 ± 0.683`, `z +1.49`, `LB95 −0.346`, `UB95 +2.384`. ⛔ It discharged nothing, licensed
nothing, and retracted nothing.

Round 1's own `READ_RULE` §8.2 pre-committed, before its game 1, that such a cell is re-runnable
**only on a NEW BAND, with a NEW PAIR, and only with FRESH OWNER FUNDING** — and that it **may not be
extended, topped up, or re-read at larger `n` on its own band** (the `rodv3` failure mode), because an
extension could not be pooled with the original anyway.

⭐ **THIS IS THAT ROUND, EXECUTED TO THE LETTER:** new pair, new band, owner-funded 2026-08-31 night,
the bar **unmoved**, and ⛔⛔ **NOTHING POOLED ACROSS THE TWO.** This round is **800 fresh decks, not
400 + 400** (§1.3).

---

## 1. THE STATISTIC

**PRIMARY:**

```
D(deck) = ( diff(deck, a_seat=0) + diff(deck, a_seat=1) ) / 2
M       = mean over decks appearing in BOTH seatings, POOLED OVER EVERY CHUNK
SE      = sample sd (ddof=1) / sqrt(n_paired)
z       = M / SE
UB95    = M + 2*SE          LB95 = M - 2*SE
```

`diff` is the harness's own final-score margin, **candidate minus opponent, in POINTS**.
**`M > 0` ⇒ the CANDIDATE won.** A deck missing a seating is **DROPPED**, never defaulted to zero, and
surfaces at `G-DECKS` and `G-N` (§4.1).

⛔ **Adjudicated AGAINST ZERO, at the cell's OWN REALIZED SE.** The sizing constant
`sigma_D = 13.6495` — ⭐ **round 1's own realized arbiter-on-both-seats dispersion**, the only such
measurement in existence (DESIGN §3.1) — is **power arithmetic only** and is ⛔ **never a denominator
in a branch test.** `se_anomaly()` REPORTS the realized/modelled ratio and it is never a branch input.

⛔ **`n_paired` IS IN DECKS, NOT GAMES.** A paired `n=1600` cell yields at most **800 decks**. Every
bar below is in **pts/deck**.

### 1.1 ⭐⭐ THE POOL IS COMPUTED FROM RECORDS, AND `RECON` IS PER CHUNK

⛔ **No `summary.json` spans the pool** — the harness never computed one, because the 800 decks were
played as 8 invocations. The primary is therefore computed by `screen_lib.paired_margin` over the
**union of every chunk's raw records**.

⭐ That implementation is **not** taken on trust: `paired_margin` is a deliberately independent
`math.fsum` re-implementation of `eval_fair_puct._paired_z` (an import would agree by construction and
witness nothing), and **`RECON` certifies it CHUNK BY CHUNK against the harness's own arithmetic** on
each chunk's real emitted `summary.json`. `READ_RULE` §1 then applies that **certified** implementation
to the union.

⛔ **A "POOLED RECON" WOULD WITNESS NOTHING** — it could only compare `paired_margin` against a number
this instrument synthesized itself. That is why the witness lives at chunk level and the statistic at
pool level, and why **a chunk-level `RECON` disagreement VOIDS the cell**.

### 1.2 THE SECONDARY — elo, and it is NOT A BAR

`elo` is reported with its own **deck-paired** CI, **on every branch**.

⚠️⚠️ **THERE IS NO ELO BAR HERE.** The bar is `+1.0 pts/deck` on the deck-paired margin, and it has
**no exchange rate into elo that this round measures**. What is printed beside the elo is the
instrument's **2σ RESOLUTION** — **`±12.3`** elo, deck-paired at 1600 games — a statement about what
the instrument can see, never a threshold anything must clear.

⭐ **R4's footing, carried:** 1600 games are 800 decks × 2 seatings, so pairing scales the sigma by
`1/√2`. The textbook binomial figure is the **unpaired** one (`±17.4` at 2σ, n=1600). ⚠️⚠️ **NOTE THE
COINCIDENCE AND DO NOT BE MISLED BY IT: `±17.4` was ROUND 1's PAIRED figure at 800 games and is ROUND
2's UNPAIRED figure at 1600.** Every emitted field **names its footing**
(`elo_sig_1sigma_paired` / `elo_sig_1sigma_unpaired`), and that is the defence.

⭐ **A disagreement between the margin and the elo is DISCLOSED, never arbitrated.** The margin
carries the branch.

### 1.3 ⛔⛔ THE CONTEXT ROWS ARE A DESCRIPTIVE OVERLAY ONLY — **INCLUDING ROUND 1's**

The seven prior fpu readings (DESIGN §4.1) — **round 1 at `168e9`**, `0.2` and `0.4` from
`fpu_resurrection`, and the ladder's `0.05 / 0.10 / 0.15 / 0.30` — plus the older neural-era screens
are **context in the read-out and nothing else**.

⛔ **NEVER POOLED. NEVER z-COMBINED. NEVER A BRANCH INPUT. NEVER INTERPOLATED.**

⛔⛔ **AND THE ROUND-1 ROW IS THE ONE MOST AT RISK OF BEING AVERAGED IN, PRECISELY BECAUSE IT IS THE
SAME AGENT PAIR.** It must not be:

- it is **still cross-band**, and CL-068 measured **1.8–2.2× over-dispersion** on exactly that class,
  in *both* the elo and the deck-paired-margin statistics, with an identity control exonerating the
  harness and the "different decks" explanation arithmetically excluded (the per-deck SEM already
  prices the deck draw);
- round 1's own `READ_RULE` §8.2 pre-committed that its cell **may not be extended or topped up**, and
  that an extension **could not be pooled with it anyway**;
- ⭐ **so "1200 decks of evidence" is an arithmetic that does not exist.** This round is **800 fresh
  decks**, read alone.

⭐ What round 1 legitimately contributes is a **design act, spent before any number of this round
exists**: its realized **DISPERSION** (`sigma_D = 13.6495`) is this round's sizing constant. Its
**MEAN** enters nothing. ⭐ It also contributes an **INSTRUMENT certificate** (§4.2) — the fact that
its archive passed every gate is evidence about the **code path**, which is a different kind of claim
from its number and is treated as such.

The six arbiter-off rows are **worse than cross-band**: a different **agent pair**, not a different
deck draw — and that is the very quantity this family exists to measure. The neural rows are cross-band
**and** cross-era **and** cross-agent **and** cross-budget.

---

## 2. THE ARMS

| side | agent |
|---|---|
| **candidate** | the DEPLOYED champion — fair PIMC `k16×1376 = 22016`, tie arbiter `B=64/J=4/argmax/tiearb2-deploy-v1/0.0/all` — **PLUS `fpu_reduction = 0.2`** |
| **opponent** | ⭐ **the SAME deployed agent, without the dose** |

⛔ **The single variable is the knob.** No `--cand-fpu-reduction` reaches the opponent side, ever;
`--c-puct` and `--tau-p` are **never** used at all (they build BOTH sides, see `G-TWOSIDED`); and there
is **no `--cand-c-puct`** anywhere in this round's launcher.

⭐⭐ **THE ARBITER IS ARMED ON BOTH SEATS AT THE FULL DEPLOYED SPEC**, including `phase_gate`. ⛔ A
cell with the arbiter on the candidate alone is a **CONFOUNDED arb+fpu cell claiming a single
variable**; `G-TIEARB-SIDES` and `G-TIEARB-FIRE` exist to make that unshippable.

---

## 3. THE KNOB — FROZEN SEMANTICS

| `fpu_reduction` | meaning |
|---|---|
| `None` / unset | the NeuralMCTS **legacy optimistic** `q = 0.0` for unvisited children — **the champion, bit-for-bit** |
| a value `r` | an unvisited child scores `q = parent.Q − r` (pessimistic FPU) |

⚠️ **`0.0` IS NOT `None`.** `Some(0.0)` takes the `node_q − 0.0` branch — the **parent's Q** — while
`None` takes the flat `0.0` branch. The two are deliberately distinguished end-to-end and never
coerced. ⛔ A gate that read `null` and `0.0` as the same value would be unable to tell the champion
from a live cell.

⚠️ `parent.Q` is already in `node.player_to_move`'s POV — the same POV the unvisited child is scored
in — so **no sign flip is applied**. `mcts.py:1225` and `carc_core::search/mod.rs:816` implement the
identical rule; the two backends **mirror**. ⛔ Rust is still mandatory: the **arbiter** is rust-only.

---

## 4. THE GATES

⛔ **ABSENT IS FAIL. Never a skip, never a default.** Every gate resolves across **both** documents —
`config.*` in **`manifest.json`**; statistics in **`summary.json`**, which carries **no config block
at all** (IS-D1) — and prints **which document and which address** answered. A value found at **no**
address is `ABSENT`, and `ABSENT` is `FAIL`.

⛔ **A FAIL ON ANY GATE MAKES THE CELL `H-VOID-INSTRUMENT`**, checked **first** in the branch table.
⛔ **The round then discharges nothing**: a voided cell is not a bound, so neither `H-ADOPT` nor
`H-BOUNDED` may be declared over it, and step 2 of the adoption chain remains **unpriced**.

⭐⭐ **PER-CHUNK GATES ARE FOLDED BY CONJUNCTION.** A gate that reads one archive's config runs on
**every chunk** and is `ok` **iff** it is `ok` on **every** one **and there is at least one chunk** —
the second clause is load-bearing, because an empty shard map would otherwise make `all()` pass
VACUOUSLY, which is the IS-D1 defect wearing a new hat.

| id | scope | asserts | address | fires on |
|---|---|---|---|---|
| ⭐⭐ `G-CHUNKS` | pool | every frozen chunk EXISTS and is COMPLETE — **manifest AND summary** — and no dir outside the frozen plan is present | the chunk out-dirs | ⛔⛔ **THE FLEXIBLE-BOX CLAUSE'S OWN FAILURE MODE, NAMED.** `eval_fair_puct` writes the manifest at run START and the summary at run END, so a chunk KILLED mid-flight (which is exactly what adding a box does to the laptop's in-flight work) has the first and not the second. ⭐ **THE FIX IS TO RESUME THAT CHUNK** — its records are cached, so the resume costs only the unplayed games. ⛔ Reading around it is not available: a summary-less chunk has no `RECON` witness, no `G-TIEARB-FIRE` aggregate and no `n_failed` accounting |
| ⭐⭐ `G-NODUP` | pool | (a) the chunks' realized deck-seed sets are pairwise **DISJOINT**; (b) every `(deck, a_seat)` appears **EXACTLY ONCE** across the pool; (c) no chunk's seeds escape **that chunk's own** sub-range; (d) no chunk realized ZERO records; (e) ⭐ the pool is non-empty and every shard is in the frozen plan | the pooled raw `seed*_a*.json` | ⛔⛔ **THE CLAUSE THE FLEXIBLE-BOX PROMISE RESTS ON.** ⚠️ (b) is strictly stronger than (a) and is the one that binds: records are keyed by `(seed, a_seat)` *inside* a dir, so a duplicate can only arise **ACROSS** dirs — which is exactly what a mis-typed `--seed-lo` on the second box produces. ⭐ (e) is an ANTI-VACUITY clause: "no duplicates among zero records" is true and meaningless |
| ⭐⭐ `G-SHARD-IDENT` | pool | every chunk resolved the **SAME two agents** — the dose, both `c_puct`s, `tau_p`, the three budget fields, both leaf hashes, `exact_k`/mode, backend, rules profile, and the **whole arbiter dict for both seats** — compared **CHUNK TO CHUNK** | `manifest:*`, chunk vs chunk | ⛔⛔ **A DEFECT INVISIBLE TO EVERY OTHER GATE.** Each chunk passes its own config gates against the FROZEN constants; a value that differs *between* chunks — a second box on a stale `WORKERS.conf` — is invisible to all of them, and pooling those chunks pools two measurements. ⭐ An address ABSENT on EVERY chunk is also a FAIL: chunks that agree because none of them says anything agree about nothing |
| ⭐⭐ `G-TIEARB-SIDES` | per chunk | **BOTH SEATS ARMED** at the full deployed dict `{enabled true, B 64, J 4, mode argmax, salt tiearb2-deploy-v1, eps 0.0, phase_gate all}` | `manifest:{cand,opp}_tiearb` / `config.{cand,opp}_tiearb` / `config.opponent.tiearb` | ⛔⛔ **THE ROUND'S OWN LIVENESS GATE.** Delegated to `tiearb_gates.assert_tiearb_sides`. ⛔ Phasegate's `G-TIEARB-ARM` is **NOT** reused: it requires *"opponent: no tiearb container"* and would FAIL this healthy cell. ⭐ **A MISSING `phase_gate` KEY IS A FAIL AND NEVER A DEFAULT** — absent means a stale wheel whose arbiter ran UNGATED, and a silently-defaulted `"all"` on a gated cell makes it BE the ungated cell |
| ⭐⭐ `G-TIEARB-FIRE` | per chunk | **BOTH SEATS ARBITRATED IN PLAY**: `*_games > 0`, `*_fired_plies_total > 0`, `*_G_FIRE_fired` is `false`, `*_partial_argmax_total == 0`, `*_B == [64]`, `*_J == [4]`, `*_phase_gates == ["all"]` | `summary.json` | ⛔⛔ **THE WITNESS `G-TIEARB-SIDES` CANNOT BE.** A config echo is exactly the class of evidence the hard-coded `fpu_reduction = None` satisfied for months. ⚠️⚠️ `*_G_FIRE_fired` **IS THE VOID FLAG BY ITS OWN NAME** — the harness sets it when `phi < 1.0` — so `false` is HEALTHY. ⚠️ `*_errors_total` is REPORTED (fail-soft), never fatal |
| ⭐⭐ `G-FPU` | per chunk | `config.cand_search.fpu_reduction == 0.2` EXACTLY (`null` distinguished from ABSENT), **and** `config.cand_search.c_puct` is `null` | `manifest:config.cand_search.*` | ⛔⛔ **THE INVERTED-LIVENESS GATE.** A harness predating the fpu plumbing emits no `cand_search` at all, and its candidate was **dose-blind by construction** — a cell over it is champion-vs-champion, moves no leaf hash, sits inside `G-SAT`'s rail and reads as a clean credible null |
| ⭐⭐ `G-TWOSIDED` | per chunk | candidate carries `0.2`, opponent carries `fpu_reduction: null`, `c_puct` EQUAL across the sides and equal to the champion's `1.5` | `manifest:config.champion.*` vs `config.opponent.champ_cfg.*` | ⛔ the **second, independent** witness for the dose. `G-FPU` proves it was *requested*; this proves it *landed*. ⚠️ It is **weaker than a play-derived witness** — the dose's play-derived evidence is the **IDENT legs** (DESIGN §9.3) |
| `G-SINGLEVAR` | per chunk | `fpu_reduction` DIFFERS across the two sides and equals `0.2` on the candidate; **every other** alias is EQUAL | `manifest:config.champion.*` vs `config.opponent.champ_cfg.*` | ⚠️ The opponent's knobs live one level down under `champ_cfg` and its **budget** one level up. ⛔⛔ **`tiearb_*` IS DELIBERATELY NOT IN THE ALIAS TABLE**: `_cfg_from_dict` reads five keys by name, so such a clause would read ABSENT and void every healthy cell |
| `G-LEAF` | per chunk | ⭐ **BOTH SIDES EQUAL** `a36d2e15a3b3d71d`, and `config.cand_leaf_cfg.v29_meeple_curve == curve125` | `manifest:config.{cand,opp}_leaf_hash` | neither the dose nor the arbiter is a leaf term |
| ⭐ `G-BAND` | pool (per chunk) | **each chunk declares EXACTLY its OWN frozen `seed_lo`**, exactly `decks_per_chunk` decks, and `seatings_per_deck == 2` | `manifest:config.band_seed_start`, per chunk | ⭐ **STRICTER THAN ROUND 1's.** A chunk launched with the wrong `--seed-lo` — the realistic two-box hand-split error — fails HERE, at its own address, before `G-NODUP` ever has to catch the overlap it would cause |
| ⭐⭐ `G-DECKS` | pool | (a) every realized seed inside `169000000000..169000000799` — **HARD**; (b) decks played at ONE SEAT ONLY are **REPORTED**, and void only at or above **2 % OF GAMES**; (c) `n_common >= 80 %` of 800 — **HARD** | pooled raw `seed*_a*.json` | ⛔ **THE CARRIED `FPU-A1` FIX** — see §4.1. ⚠️ It reads the **BAND**; a seed inside the band but outside its own CHUNK is `G-NODUP`'s, and a chunk that never ran is `G-CHUNKS`'. All three are needed and none subsumes another |
| ⭐⭐ `G-N` | pool | `n` and `n_failed` **SUMMED over every chunk's own `summary.json`**; the **accounting identity** `Σn + Σn_failed == 1600`; `Σn_failed / 1600 < 2 %`; `n_common >= 80 %` of 800 | each chunk's `summary.json` | ⛔ **THE CARRIED `FPU-A1` FIX** — and ⭐⭐ **THE IDENTITY IS ALSO THE FLEXIBLE-BOX TILING CHECK**: `Σn + Σn_failed == 1600` can only hold if the chunks' assigned ranges COVERED THE WHOLE BAND, so a two-box split that left a hole fails HERE loudly instead of producing a short pool that reads like a complete round |
| `G-BUDGET` | per chunk | both sides `(k_dets, sims_per_det, total_sims) == (16, 1376, 22016)` **and the product multiplies out** | `manifest:config.{champion,opponent}.*` | any asymmetry, and a **stale 11008** cell |
| `G-PROD` | launcher | ⭐ **PRE-COMPUTE.** the frozen **budget AND arbiter dict** == `governance/PRODUCTION.yaml` `champion.fair_deploy` | `governance/PRODUCTION.yaml` | ⛔ Hard abort for a real chunk and for the smoke; loud-but-continue for `--dry-run`/`--plan`. ⚠️ `PRODUCTION.yaml` carries **no `phase_gate` key** — the deployed arbiter is UNGATED and `"all"` is how the harness spells that; the absence is asserted explicitly rather than defaulted. **The fix is the bundle sync, never an edit to the pair** |
| `G-EXACT` | per chunk | both sides `exact_k == 2` and `mode == "marginalized"` | `manifest:config.endgame.*` | K=3/4 are clairvoyant-only |
| `G-RULES` | per chunk | `rules_profile.name == "fixed_v1"`, `r9_env_ok` and `r9_env_observed` both `true` | `manifest:rules_profile.*` | R9 not latched. ⚠️ R9 is env-latched at **import** |
| `G-BACKEND` | per chunk | `name == requested == "rust"`, `mixed_builds false`, `converted_sides == {candidate, opponent}` | `manifest:config.backend.*` | ⛔⛔ **RUST IS NOT OPTIONAL HERE.** The tie arbiter is RUST-ONLY and the harness refuses `--{cand,opp}-tiearb-enabled` on python — so a python leg could not arm either seat and would silently be the arbiter-off cell this family exists to stop being |
| `G-WHEEL` | per chunk | `carc_rs_build` and `carc_rs_binary_sha` present; `mixed_builds false` | `manifest` | ⚠️ `carc_rs_version` is permanently `"0.1.0"` and is **NOT** a discriminator |
| `G-WHEEL-SAME` | round | ⭐ **ONE wheel WITHIN each box**, per chunk, bucketed by strictly-resolved host | `manifest:carc_rs_binary_sha` | a box that rebuilt its wheel MID-ROUND. ⚠️⚠️ **The sha is BOX-LOCAL BY CONSTRUCTION** — two boxes compiling identical source produce different bytes — so it is **REPORTED, never compared, ACROSS boxes.** A cross-box sha comparison would void every healthy two-box round and is the IS-A1 defect in a new place |
| `G-REV` | round | (i) **every box** that played publishes a `PINNED_SRC_REV` and they are the **SAME 40-hex sha**; (ii) every chunk's short `code_rev` canonicalizes to it (`cross_box_rev_gate`); (iii) `SRC_CLEAN_*.jsonl` records the code paths clean at both boundaries of every chunk | manifests + each box's `PINNED_SRC_REV` | ⛔⛔ **THE ROUND'S PRIMARY PROVENANCE RISK, AND THE FLEXIBLE-BOX CLAUSE MAKES IT WORSE.** BOTH the fpu plumbing AND the `--opp-tiearb-*` plumbing are **python-only**, so a box on stale source serves a **dose-free candidate** and/or an **UNARMED OPPONENT** with a healthy `carc_rs_build`, a healthy binary sha and the correct leaf hash. ⛔ A box added mid-round was not on the launch checklist and is the **more** likely offender. ⛔ **NEVER by comparing one box's emitted short rev to another's** — the IS-A1 defect |
| `G-BLIND` | round | `BLIND_COMMIT` is a 40-hex sha, stamped into **every** chunk's manifest, and they agree | `manifest:BLIND_COMMIT` | a read that was not blind |
| ⭐⭐ `G-HOST` | pool | **PROVENANCE-ONLY.** Publishes the chunk → host → role → realized-range map. FAILS only on (a) a chunk whose manifest carries **NO** `host`, or (b) a host that is **not one of the two funded boxes** | `manifest:host`, per chunk | ⛔⛔ **A DELIBERATE DOWNGRADE FROM ROUND 1**, which VOIDED a cell run off its frozen box. `DESIGN.md` §6.4 pre-registers box assignment as THROUGHPUT-ONLY and explicitly permits it to change mid-round; a gate that voided on the box would make the owner's own funded flexibility unusable. ⛔ **THERE IS NO CLAUSE ON WHICH BOX PLAYED WHICH CHUNK AND NONE ON THE SPLIT RATIO — any tiling is legal.** What it still refuses is a **destroyed provenance map**: an absent host, or an archive from a box nobody funded. ⚠️ It uses `host_role_strict`, NOT `host_matches_box`, whose *"not the laptop ⇒ local"* catch-all would launder an unfunded box into a clean provenance line (DESIGN §7.4) |
| `G-SAT` | pool | `0.35 <= winrate <= 0.65`, recomputed from the **pooled** records | pooled raw records | a **RAIL** check, not a strength bar: both sides run the same search on the same leaf at the same budget with the same arbiter, so a winrate outside this window means the two sides are not the agents this design says they are. ⚠️ Round 1 read `summary:winrate`; no summary spans this pool, so it is recomputed by the implementation `RECON` certifies. ⭐ The rail belongs on the POOL — a per-chunk rail at 100 decks would be a ±4σ band and would catch nothing |
| `RECON` | per chunk | §1.1's witness agrees on all five statistics, in **EVERY** chunk | each chunk's `summary.json` vs its raw records | ⛔ can only VOID, never move, a number |

⚠️ **REPORTED, NEVER A GATE: `config.opponent.production_config_deviations`.** The harness stamps it
against `PRODUCTION.yaml`; on 2026-08-31 the loader was stale and stamped a FALSE deviation on a
healthy cell. `G-BUDGET` is the gate, and it reads the manifest directly.

### 4.1 ⭐⭐ `G-N` AND `G-DECKS` ARE THE PROSE — THE CARRIED `FPU-A1` FIX

`fpu_resurrection`'s `CELL_FPU04` was **VOIDED** by its own adjudicator over **one** deterministic
`WindowTruncationError` (`1/800 = 0.125 %`), an order of magnitude below the 2 % void bar its **own
frozen prose** set, because a **condition column was stricter than the prose beside it**.

**Here the prose IS the condition, in both gates, on ONE denominator:**

- ⭐⭐ **THE DENOMINATOR IS GAMES.** A deck played at one seat only **is** exactly one failed game, so
  `G-DECKS`' one-seat-only rate and `G-N`'s `Σn_failed / n_games` are the **same quantity read off two
  different documents**.
- **`Σn_failed / 1600 < 2 %`** ⇒ **REPORTED** in the gate's own `why`, and the cell **READS**.
- **`>= 2 %`** ⇒ the cell **VOIDS**, on both gates.
- **`n_common >= 80 %` of 800** — a **fraction**, never an equality. ⚠️ A **backstop**: at 800 decks
  the 80 % floor allows 160 lost decks while the 2 % bar voids at 32 games, so the 2 % bar is the
  operative one and the floor catches a shape it cannot see.
- ⛔ **The accounting identity `Σn + Σn_failed == 1600` is a HARD fail and is NOT absorbed by the
  bar.** ⭐⭐ **AND IT IS ALSO THE TILING CHECK** (§4's `G-N` row).
- ⛔ **Out-of-range seeds remain HARD fails.**

⭐ **A seeded game cannot be re-rolled.** A permanently-failing deck is a fact about the deck set, not
about the dose; the emitter states EXCLUSIONS, not zeros.

`analyze_h2h.py --selftest` proves **both directions at the frozen 800-deck scale**: `31/1600 =
1.9375 %` must READ on both gates; `32/1600 = 2.000 %` must VOID on both.

### 4.2 ⭐⭐ THE GOLDEN GATE IS INHERITED — A LAUNCH PRECONDITION, NOT A GATE

`../fpu_ladder_prep/FPU_BITEXACT_LADDER.json` must read `PASS`, **carrying the launching box's own
`carc_rs_binary_sha`**, before that box plays; `run_cells.sh` refuses without it. It proves `fpu=None`
is the champion bit-for-bit on that wheel, and that the dose binds at `0.05 / 0.1 / 0.15 / 0.3`
(`DOSE-DISTINCT`).

⭐⭐ **ROUND 1 ADDS A THIRD SOURCE, AND ITS STATUS IS EXACT:** round 1 played 800 games of the **exact
arms of this cell** and cleared every gate in this family, including `G-TIEARB-SIDES` and
`G-TIEARB-FIRE` on both seats. ⛔⛔ **THAT IS AN *INSTRUMENT* CERTIFICATE, NOT A STATISTICAL ONE** —
its **number** is a context row that is never pooled (§1.3); the fact that its **archive passed the
gates** is evidence about the **CODE PATH** and is inherited as such. ⚠️⚠️ **AND IT IS INHERITED PER
BOX**: it was banked on the **laptop**, so ⛔ **the local box has never run a gate-passing cell of this
family.**

⛔⛔ **TWO GAPS REMAIN AND ARE NOT WAVED THROUGH:** (1) no certificate has ever exercised `fpu` AND the
arbiter TOGETHER; (2) `0.2` is not one of the ladder gate's four control doses. ⭐ **THE `--smoke`
IDENT LEGS PAY THEM** (`IDENT-REPRODUCES` and `POSITIVE-ARB-ON`), and they are ⭐ **MANDATORY PER BOX**.

⚠️ Both are **code-path** gates at a tiny budget (`k2 × 96`). ⛔ **No number in either is a strength
measurement.**

### 4.3 The reachable branch set, stated BEFORE the run

Recorded here so it cannot be reconstructed later: **every branch in §5 is reachable**, including
`H-NEGATIVE` and `H-VOID-INSTRUMENT`. ⛔ No branch is unreachable by construction; the selftest sweeps
a dense `(M, SE)` grid — including this round's own `se = 0.4826` — and proves it.

---

## 5. THE BRANCHES — PRE-REGISTERED, EXCLUSIVE, EXHAUSTIVE

Adjudicated on the cell's own realized SE, against zero, **in this order**. First match wins.

| # | branch | condition | reading |
|---|---|---|---|
| 0 | **`H-VOID-INSTRUMENT`** | any §4 gate FAILS, or any round-level gate fails, or the archive is ABSENT | The instrument, not the world. **No reading of any kind.** ⛔ Step 2 of the adoption chain remains **UNPRICED** |
| 1 | **`H-NEGATIVE`** | `M <= 0` **and** `z <= -2.0` | ⭐ **THE DOSE IS ACTIVELY HARMFUL IN THE DEPLOYED CONFIGURATION.** Pre-registered and mechanistically plausible: the arbiter fires on exact ties and a pessimistic FPU changes which ties are REACHED |
| 2 | **`H-ADOPT`** | **`LB95(M) >= +1.0`** | ⭐⭐ **THE EFFECT SURVIVES INTO THE DEPLOYED CONFIGURATION** at the size the decision cares about. ⚠️ Licensed reading is **narrow** — see §5.2 |
| 3 | **`H-BOUNDED`** | **`UB95(M) < +1.0`** | ⭐ **BELOW the decision-relevant effect at 95 %, in the configuration that ships.** It DISCHARGES step 2. ⚠️ It **bounds; it does not zero** |
| 4 | **`H-UNRESOLVED`** | everything else | ⛔ **NOT a null and NOT a bound.** `feedback_noisy_plateau_not_a_conclusion` binds |

⛔ **Exclusive and exhaustive by construction.** `H-ADOPT` and `H-BOUNDED` cannot both hold
(`LB95 <= UB95`). `H-NEGATIVE` requires `M <= 0 ∧ z <= -2`, which forces `UB95 <= 0 < 1.0`, so it
would **also** satisfy `H-BOUNDED` — which is why it is checked first.

⭐⭐ **THE BAR IS ON THE INTERVAL, NOT THE POINT ESTIMATE.** At this round's `se = 0.4826`, `M = +1.5`
— a point estimate half again the bar — reads `H-UNRESOLVED`, because `LB95 = +0.535`. `sanity_check()`
pins that, and pins it at **both** rounds' `se`.

### 5.1 ⭐⭐ THE BRANCH TABLE, AS CONSEQUENCES

| branch | what happens next |
|---|---|
| `H-ADOPT` | ⭐ **PROPOSE** (a) a `governance/PRODUCTION.yaml` change setting the champion's `fpu_reduction` to `0.2`, and (b) funding **step 3** (Carcasum external). ⛔ **BOTH ARE PROPOSALS.** The flip needs an OWNER RULING, exactly as the k16 and `B=64` folds did |
| `H-BOUNDED` | ⭐ **DISCHARGE step 2.** The effect does not survive into the deployed configuration at `+1.0`; the flip is not worth proposing and step 3 is not worth funding. Update `docs/LEVER_INDEX.md:146` to say so |
| `H-NEGATIVE` | ⭐ **DISCHARGE step 2, with a stronger statement.** No production change either way — the champion already runs `fpu=None` |
| `H-UNRESOLVED` | ⛔ **NOTHING IS DISCHARGED AND NOTHING IS PROPOSED.** §8.2 pre-commits the price and ⛔⛔ **§8.3 pre-commits that it does NOT fund a round 3** |
| `H-VOID-INSTRUMENT` | ⛔ **NOTHING.** Fix the instrument; a re-run is a NEW round on a NEW band with fresh owner funding |

### 5.2 ⚠️ THE RIDERS ON `H-ADOPT` — MANDATORY, AND THEY TRAVEL WITH EVERY CITATION

1. ⛔⛔ **IT DOES NOT LICENSE A PRODUCTION CHANGE — IT LICENSES *PROPOSING* ONE.**
   `governance/PRODUCTION.yaml` is UNTOUCHED on every branch of this round.
2. ⛔ **THE OUT-OF-FAMILY CHECK COMES BEFORE ANY GENERAL CLAIM.** `feedback_evloss_grader`'s F4
   lesson: a `+1.49` in-family ceiling read `−0.64` at `z −3.8` out-of-family on the same CRN worlds.
3. ⛔ **IT DOES NOT LOCATE AN OPTIMUM AND IT IS NOT A BRACKET.** One dose, one band.
4. ⛔ **IT SAYS NOTHING ABOUT THE ARBITER-FREE CHAMPION.** No reading here may be quoted back onto the
   `155e9` / `164–167e9` cells.
5. ⚠️ **TYPE-M RIDER.** The funded `n=800` is powered ~98 % against a repeat of the incumbent's
   `+2.951`, ~53 % at a true `+2.0`, ~39 % at `+1.835`, and only ~2.5 % at **round 1's own `+1.019`**.
   ⛔ **The smallest true effect this round adopts at even coin-flip odds is `+1.97 pts/deck`.** A cell
   that adopts near the bar carries a **magnitude biased upward**; the SIGN is the reliable part.
6. ⚠️ **IT IS A `k16 × 1376`, `B=64`-BOTH-SEATS, `fixed_v1`+R9, exact-k2-marginalized, rust result on
   ONE fresh band, executed on ONE OR TWO BOXES.** The box split is provenance and is published in
   `G-HOST`'s map.
7. ⚠️ **`elo` may never be quoted bare**, and here it is not even a bar (§1.2).
8. ⛔⛔ **IT IS NOT "1200 DECKS".** It is 800 fresh decks on `169e9`. Round 1's 400 are never pooled
   (§1.3).

### 5.3 ⛔ ONE CELL — THE MULTIPLICITY NOTE

There is **no multiplicity to correct**: one cell, one pre-registered bar, one question. ⭐ At the
`LB95` bar the false-adopt rate under a true null is **≈ 0.002 %** — **this bar cannot fire on noise**.

⛔ **AND THE TWO ROUNDS ARE NOT A MULTIPLE-COMPARISONS FAMILY EITHER** — not because they were
corrected for, but because **round 1 discharged nothing and is pooled with nothing.** A reader who
wants to treat them as two shots at the same bar is asking for the pooling §1.3 forbids.

---

## 6. ⭐⭐ THE FLEXIBLE-BOX CLAUSE — WHAT THE READ DOES WITH IT

Pre-registered in full at `DESIGN.md` §6.4. What binds **the read**:

- ⭐ **THE READ POOLS EVERY RECORD ON THE ONE BAND.** The chunking and the box split are execution,
  not measurement.
- ⭐ **`G-HOST` IS PROVENANCE-ONLY.** It publishes the chunk → host → range map. ⛔ **No bar, gate or
  branch reads which box played what**, and **any tiling is legal**.
- ⛔ **`G-NODUP` OWNS THE PROPOSITION THAT THE RANGES DID NOT OVERLAP**, and `G-CHUNKS` that they
  covered the band completely — the latter reinforced by `G-N`'s summed accounting identity.
- ⭐⭐ **NO CROSS-BOX STATISTIC EXISTS, SO CROSS-BOX FLOAT IDENTITY IS NOT RELIED ON.** Both seatings
  of every deck are played inside **one chunk on one box**, so `D(deck)` is computed entirely within a
  box; the box is a factor **common to both arms** of every contrast that enters the statistic and
  **cannot bias candidate-minus-opponent**. A box difference could only add between-deck dispersion,
  which the realized SE already prices. ⛔ **No quantity computed on one box is ever differenced
  against one computed on another.**
- ⛔ **WHAT *IS* REQUIRED ACROSS BOXES IS SOURCE IDENTITY**, and that is `G-REV`'s
  (`cross_box_rev_gate`, the IS-A1 fold). ⚠️ `carc_rs_binary_sha` is box-local by construction, so
  `G-WHEEL-SAME` asserts one wheel **within** each box and **reports** the shas across them.

---

## 7. THE ADOPTION CHAIN — FROZEN BEFORE ANY NUMBER EXISTS

1. **THE PARENT SCREEN / THE DOSE LADDER** — ⭐ DONE: `fpu=0.2` read `F-RESURRECT` (`+2.951`, band
   `155e9`, arbiter OFF); the ladder that bracketed it read `LADDER-UNRESOLVED` (`164–167e9`).
2. ⭐⭐ **THE PRODUCTION H2H** — the dose vs the DEPLOYED champion with the arbiter ARMED ON BOTH
   SEATS, on a FRESH band. ⛔ **THE LEG THAT PRICES THE ARBITER-OFF DEVIATION.** ⚠️ **ROUND 1**
   (`168e9`, `n=400`) read `H-UNRESOLVED` and discharged nothing; **THIS IS ROUND 2** (`169e9`,
   `n=800`), a separate owner-funded round whose numbers stand alone.
3. **CARCASUM EXTERNAL** — the arm-on T-TRANSFER protocol, the only out-of-family check this program
   has.
4. **E4 EPOCH** on the phone.

⛔ **EACH LEG IS ITS OWN PREREG, ITS OWN BAND AND ITS OWN OWNER FUNDING.** A cell firing here funds
nothing automatically.

---

## 8. ⛔⛔ CAVEAT — WHAT THE BAR COSTS, STATED BEFORE GAME 1

*This section exists because the house rule (owner, 2026-08-30) requires it. ⛔ **THE BAR DOES NOT
MOVE** — `BAR_EFFECT = 1.0` is round 1's pre-registered design, carried verbatim, and this section
changes no number, no gate and no branch.*

**At the modelled `se = 0.4826` (n = 800 decks), computed by `read_distribution` and asserted by
`sanity_check`:**

| true effect `δ` | `H-ADOPT` | `H-BOUNDED` | `H-NEGATIVE` | `H-UNRESOLVED` |
|---|---:|---:|---:|---:|
| **0 (true null)** | 0.002 % | **50.6 %** | 2.28 % | 47.1 % |
| **+1.0 (at the bar)** | 2.28 % | 2.27 % | ~0 % | **95.4 %** |
| ⛔⛔ **+1.019 (ROUND 1's OWN point estimate)** | **2.5 %** | 2.1 % | ~0 % | **95.4 %** |
| **+1.835 (the ladder's largest point estimate)** | 39.4 % | ~0 % | ~0 % | 60.6 % |
| **+2.0** | 52.9 % | ~0 % | ~0 % | 47.1 % |
| **+2.951 (a repeat of the incumbent)** | **97.9 %** | ~0 % | ~0 % | 2.1 % |

**The same table at ROUND 1's `n` (`se = 0.6825`), so the delta is visible rather than claimed:** a
true null gave `H-BOUNDED` **27.4 %** / `H-UNRESOLVED` **70.3 %**; the incumbent adopted **80.5 %**.

- ⭐ **WHAT DOUBLING `n` BOUGHT:** the bounding direction nearly doubled (27.4 % → 50.6 %), the
  unresolved mass under a true null fell 70.3 % → 47.1 %, and a repeat of the incumbent went 80.5 % →
  97.9 %.
- ⛔⛔ **WHAT IT DID NOT BUY — THE ROUND'S CENTRAL LIMITATION: IF THE TRUE EFFECT IS WHAT ROUND 1
  MEASURED, THIS ROUND IS BLIND TO IT.** At `δ = +1.019` it reads `H-UNRESOLVED` **95.4 %** of the
  time, and 80 % adopt power there would need **4,279,208 decks**. ⛔ No affordable round resolves an
  effect that size.
- ⭐ **THE HONEST ONE-NUMBER SUMMARY:** the smallest true effect this cell adopts at even coin-flip
  odds is **`+1.97 pts/deck`**.
- ⭐ **The bar cannot fire on noise** (0.002 % false-adopt).

### 8.1 ⛔ THE `n` THIS BAR WOULD ACTUALLY NEED

| goal | decks | games | vs funded |
|---|---:|---:|---:|
| **funded** | **800** | **1600** | 1× |
| adopt a repeat of `+2.951` at 80 % power | 396 | 792 | 0.5× ⭐ |
| adopt `+2.0` at 80 % power | 1,505 | 3,010 | 1.9× |
| adopt `+1.835` at 80 % power | 2,158 | 4,316 | 2.7× |
| `H-BOUNDED` at 80 % under a true null | 1,505 | 3,010 | 1.9× |
| ⛔⛔ adopt `+1.019` (round 1's estimate) at 80 % power | **4,279,208** | 8,558,416 | **5,349×** |

### 8.1a ⛔⛔⛔ THE BAR HAS COLLIDED WITH `2σ̂` AT THIS `n`, AND IT IS DISCLOSED

**Found by this round's own `sanity_check()`.** At `n = 800`, `2 · se_model = 0.9652` and the bar is
`+1.0` — the coincidence the owner's 2026-08-30 ruling names as a defect.

⭐ **The bar does not move, and the reason is provenance.** The ruling forbids a bar *defined as*
`2·se_model` — read off the instrument instead of off the decision. This one was derived in round 1
from two realized production folds and is carried verbatim; at round 1's `n` it sat at `0.73 · 2σ̂`.
⛔ Moving it now, after seeing round 1's `M = +1.019`, would be choosing a bar from the data — the
strictly worse sin.

⛔⛔ **BUT THE PATHOLOGY IS REAL AND IS PRICED.** `H-BOUNDED` requires `M < BAR − 2se = +0.034`, so
**the kill branch effectively needs a non-positive point estimate**, and a true null splits ~50.6 % /
~47.1 %. That is computed above, asserted in `sanity_check`, carried in
`screen_lib.BAR_COINCIDENCE_AT_FUNDED_N`, and surfaced in every read-out. ⭐ Stating it before game 1
is exactly what the house rule demands of a round that can afford only one direction.

### 8.2 ⭐ THE PRE-COMMITTED PRICE OF AN UNRESOLVED READ

**An `H-UNRESOLVED` cell is re-runnable ONLY on a NEW BAND and ONLY with fresh owner funding** — the
clause round 1 wrote and this round obeyed. Restated so the cost is known before it is incurred:

- ⛔ **The band is spent either way.** §9 retires `169e9` `decision_influenced=yes` when the read-out
  lands. The cell **may not be extended, topped up, or re-read at larger `n` on its own band** — that
  is the `rodv3` failure mode, and CL-068's cross-band over-dispersion means the extension could not be
  pooled with the original anyway.
- ⛔ **This read-rule is spent when the read-out lands, on every branch.**
- ⛔ **`H-UNRESOLVED` DOES NOT DISCHARGE STEP 2 AND DOES NOT LICENSE STEP 3.** The temptation
  afterwards will be to read a null-shaped `H-UNRESOLVED` as if it were `H-BOUNDED` — they are the
  same underlying world much of the time. It is not licensed.
- ⛔ **AND IT DOES NOT RETRACT THE ARBITER-OFF `+2.951` EITHER.**
- ⚠️ `RIDERS_H_UNRESOLVED` (in `screen_lib.py`) **GOVERN** the read-out and travel with every citation.

### 8.3 ⛔⛔⛔ AND A **SECOND** UNRESOLVED READ DOES NOT FUND A ROUND 3

**Pre-committed here, before game 1, because this is the first moment it can be.**

Round 1 read `H-UNRESOLVED` at `n=400`. This round doubled `n`. If it reads `H-UNRESOLVED` again, the
temptation will be to double again — and §8.1 shows exactly where that road goes: resolving round 1's
own point estimate needs **over four million decks**.

⭐ **The honest reading of a second unresolved round is that THE AXIS IS BOUNDED ABOVE BY WHAT THE
PROGRAM CAN AFFORD, NOT BY WHAT IT HAS MEASURED**, and the correct next act is to **write that down in
`docs/LEVER_INDEX.md:146` and STOP** — recording that `fpu=0.2` in the deployed configuration was
measured twice, at `n=400` and `n=800`, against a `+1.0 pts/deck` decision bar, and resolved neither
way; that the effect, if real, is smaller than this program can price; and that re-opening the lever
needs a **new mechanism argument, not more `n`**.

⛔ **Escalating `n` after each unresolved read is the `rodv3` failure mode wearing a new band each
time.** `project_rodv3_fullbudget_flywheel` is retired for exactly that shape, and this clause exists
so this family does not walk into it one doubling at a time. ⚠️ An owner may of course fund anything;
this clause binds **the pair's own recommendation**, which is the thing a prereg can bind.

---

## 9. GOVERNANCE

Measurement only. On **every** branch:

- ⛔ `governance/PRODUCTION.yaml` **UNTOUCHED**. `H-ADOPT` licenses **proposing** a change.
- One `experiments/results.csv` row, citing the branch and carrying §5.2's riders.
- ⭐ **`docs/LEVER_INDEX.md:146` is UPDATED on every branch** — it must say that the dose was measured
  **in the deployed configuration**, at what `n`, at what bar, and with what bound. ⭐ On an
  `H-UNRESOLVED` it must additionally carry §8.3's statement.
- Band `169000000000` retires `decision_influenced=yes`.
- ⭐ **THIS READ-RULE IS SPENT WHEN THE READ-OUT LANDS, ON EVERY BRANCH.**
- The context rows — **including round 1's** — are **context in the read-out**, never a gate input,
  never pooled (§1.3).
- ⭐ **The `G-HOST` provenance map (chunk → host → realized range) is published in the read-out on
  every branch**, because the round pre-committed to answering *"which box played which range"*.
