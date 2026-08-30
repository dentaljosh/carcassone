# S1 — OPPONENT-MODEL ASYMMETRY IN THE CHAMPION'S SEARCH

> # ✅ BUILD DONE · ⏳ G1 READY (not yet run) · ⛔ CELLS AWAIT G1
>
> **Status 2026-08-30.** Owner funded the build (verbatim *"s1 go"*), with the §11
> questions answered: **Q1** n=1,200 as scoped · **Q2** mask 31 · **Q3** three arms ·
> **Q5** arbiter OFF · **Q6** stop on `NO-EXPRESSION`. **Q4** (the `CL-083` falsifier
> amendment, §5.5) is **deferred to close-out** and is NOT adopted by this build.
>
> | gate | state |
> |---|---|
> | **G0** build + wiring + the §9.2 positive control | ✅ **DONE** — `JrPriorScope::Opp` shipped, all seven plumbing sites, 6 new rust gates + 20 python tests green |
> | **G1** EXPRESSION | ⏳ **READY, NOT RUN.** Read rule committed first: [`READ_RULE_G1.md`](READ_RULE_G1.md). Runner: [`run_g1.sh`](run_g1.sh). The full pass is the orchestrator's to launch in a quiet window. |
> | **G3 / G2 / G4 / G5** | ⛔ **not started, not funded.** Gated on G1 per §6 and the owner's Q6 answer. |
>
> **Still true: 0 games · 0 cells · 0 `results.csv` rows · 0 claims · 0 band ·
> `PRODUCTION.yaml` untouched · `governance/` untouched.** The champion's default
> traffic is byte-for-byte unchanged (dose 0 short-circuits before the scope is read;
> pinned by `jrules_prior_dose0_with_scope_opp_is_bit_identical`).
>
> **Two measured deviations from this document, both in §9.2's direction of caution:**
> 1. **§9.2 leg (b) runs at 1376 sims on the POOLED root, not 256 sims on the root
>    visit counts.** Measured, not assumed: at 256 sims `scope=opp` is *entirely*
>    unexpressed on all three probe roots — identical `node_count`, `root_w` bits, root
>    visits **and** pooled stats — despite the gate firing at hundreds of opponent
>    expansions; and even at 1376 the raw root visit counts move on only 2 of 3 roots,
>    while `pooled_stats` (the surface the PIMC pool actually argmaxes) moves on 3 of 3.
>    Both halves are pinned as rust gates. **That 256-sim flatline is itself a real
>    pre-G1 prior: this surface needs depth to express at all.**
> 2. **§9.2 leg (c) is checked WITHIN each tree**, not as a cross-scope set comparison —
>    the three scopes' trees diverge the moment a prior moves, so a cross-tree union
>    would not add up. The per-search expansion census (`jr_expansions_{total,
>    own_mover,boosted}`) makes the identity exact and non-vacuous.
>
> Companion sizing: [`SIZING.md`](SIZING.md). Everything below §0 is the design as
> funded and is unchanged.
>
> <details><summary>Original pre-build banner (historical)</summary>
>
> > ⚠️ DESIGN ONLY — NOTHING IS BUILT, NOTHING IS FUNDED, NO BAND IS CLAIMED.
> > 0 games · 0 cells · 0 `results.csv` rows · 0 claims · `PRODUCTION.yaml` untouched ·
> > no `src/` or `rust/` file changed by this document. Every number below is read off
> > an artifact already on disk and cited to it. This is a proposal for the owner to
> > fund, decline or re-shape; it pre-registers nothing until he says so and a
> > `READ_RULE.md` is committed *before* any statistic is read.
> >
> > Funded as design work 2026-08-30 (owner, verbatim *"yes, I buy a and b. engineers
> > on them"*), route (a).
>
> </details>

---

## 0. THE RECOMMENDATION IN ONE PAGE

**What S1 is.** Put an invasion-capable opponent model at the **opponent's decision
points inside the champion's own PIMC search**, so that contested-value futures are
*visited* and therefore *priced* by the champion's own leaf. Today the champion's search
plays both seats with the champion's own priors; its internal opponent never steals, so
"my big open farm is safe" is priced true and defence is priced worthless. That is
`CL-083`'s by-construction blind spot, quoted verbatim in its own row:

> *champion-continuation futures price defense/steering value ~0 by construction (the
> continuation estimand is policy-conditional)*

**The recommended mechanism (option i-a).** Add one variant — `JrPriorScope::Opp` — to
the *already built, already gated, already deploy-measured* J-rules policy-prior surface
(surface B). It boosts the expansion priors **only at nodes where the opponent is to
move**, using the anchor's own rules (which include the restored J2 farm-steal JOIN
predicate — the invasion predicate). The leaf value the search backs up is untouched on
every path, no leaf hash moves, and the champion's own move ordering is unchanged.
**Build: ~1 agent-day** (an enum variant, three string match sites, a new positive
control, tests). It is the cheapest mechanism-bearing change available by a wide margin.

**The load-bearing distinction.** Surface B was measured at `scope=all` and read a clean
null (n=800, deck-paired margin −0.0175, z −0.0282). `all` = own-nodes **+** opp-nodes.
S1 is the **opp-nodes component alone**. So S1's live hypothesis is *precise and
falsifiable*: **the own-node component is negative and cancels a positive opponent-node
component.** The first half of that has independent support across four measured rows
(surface A −2.49 pts/deck; `CL-080` −53.8/−190.3 elo; `CL-082` own-side-only asymmetric
open-city −176.10 elo). The second half is what S1 buys. §4 does that arithmetic honestly,
including what it implies for the size we must be powered for (**≈+1 pt/deck, not +2**).

**The ruler gap, confronted (§5).** `CL-083`'s falsifier names *"a validated
exploit-expressing opponent"*. **No such opponent exists and none is in reach**: S0v2 is
parked at the script ceiling (its invasions tie and deny nothing), and the shape-B
"invader" used as the C-ladder instrument **does not actually invade** (roadmap rider,
2026-08-30). I do **not** propose to manufacture one. I propose to replace the
unattainable clause with two judge-free tests that *are* attainable — a **structural
signature** read (does S1 build a different board?) and a **self-anchored deploy-budget
margin** — and to say out loud that "recovers ≥2 pts/game against an exploiter" stays
**unfalsifiable** until an exploiter exists. §5.4 also notes that the decomposition
control arm (`scope=own`) is the program's cheapest remaining *attempt* at building one.

**The gate sequence (§6), cheapest-informative-first.**

| gate | what it is | games | cost | kill power |
|---|---|---:|---:|---|
| **G0** | build + bit-identity + the **new** interior positive control | 0 | ~0 | wiring only |
| **G1** | **EXPRESSION** — scope=`opp` pick-flip + root-visit TV on banked E4 plies at the CURRENT deploy budget, under a read rule committed first | 0 | ~13 worker-h | ⭐ **the real kill gate** |
| **G3** | the three-arm decomposition cell (`opp` / `own` / `all`) vs the unmodified champion, 22016 both sides, one band, one shared deck set | 3,200 | ~459 worker-h ≈ 9.2 h two-box | the verdict |
| **G2** | **SIGNATURE** — Stage-A census of G3's own banked archives | 0 (rider) | minutes | necessary-not-sufficient |
| **G4** | guards, **only if G3 fires**: non-regression vs Carcasum @5000 ms | 400 | ~40 worker-h | deployability |
| **G5** | E4 volume with S1 armed | owner | — | corroboration only, never a verdict |

**Total to a verdict: ~474 worker-h ≈ 9.5 h two-box wall, plus ~1 agent-day of build**
(≈359 worker-h / 7.2 h at the cheaper n=800-per-arm sizing — see `SIZING.md` §4.1, which is
where the n choice is actually argued and where the design's most uncomfortable number
lives). For scale: invasion round 3 cost 171 core-h and `h2h_22016` cost 149 worker-h.

**What I would tell the owner if he wants one sentence:** *S1 is a one-day build on an
existing gated surface that tests a precise, pre-stated decomposition of a measured null,
it is powered for the effect size that decomposition actually implies only if we size for
+1 rather than +2, and its estimand cannot be closed against a real exploiter because the
program does not have one — so fund it as a decomposition, not as a defence measurement.*

---

## 1. THE CLAIM THIS SERVES

`governance/CLAIM_REGISTRY.csv` row `CL-083` (ACTIVE, high):

* Conclusion: the owner's ~10–20 pt/game edge is **position-steering plus cross-game
  adaptation**, not per-move superiority; **no per-ply intervention of any measured family
  touches it** (four judge-free instruments converge).
* Named limitation: *"champion-continuation futures price defense/steering value ~0 by
  construction (the continuation estimand is policy-conditional)"*.
* Named falsifier: *"a plan-level mechanism (board-construction shaping or **opponent-model
  asymmetry**) recovering ≥2 pts/game vs a validated exploit-expressing opponent without
  regressing vs champion+Carcasum; OR the owner's edge collapsing vs an unfamiliar
  equal-strength opponent"*.
* Surviving routes named in the row: **opponent-model asymmetry**, adaptation-share
  measurement, E4 volume.

S1 is the first of those three. The third instrument in `CL-083`'s convergence — the
invasion leaf-term family, three screen rounds, zero 2σ cells — is *closed-as-explained*,
and the explanation matters here: it closed on the **leaf/evaluation** surface. S1 is on
the **search/opponent-policy** surface, which is a different object (§7).

---

## 2. THE MECHANISM SURFACE — WHERE OPPONENT DECISIONS ARE VALUED

All line numbers are `rust/carc/carc-core/src/search/mod.rs` at `d3aae297` unless stated.

### 2.1 The three places the opponent exists inside a move

1. **`fair::FairAgent::pimc_move`** (`rust/carc/carc-core/src/fair/mod.rs`) — draws
   `k_dets` determinized worlds, runs one `Searcher::search` per world, pools the root
   `(N, W)` and argmaxes. `FairConfig` carries **exactly one** `SearchConfig` (line 65-79),
   so today there is **no per-side configuration inside a search** — the opponent is the
   champion by construction, and that is the whole of `CL-083`'s "PIMC assumes its opponent
   is itself".
2. **`Searcher::evaluate`** (line ~604) — the expansion. `mover = g.state.current_player`;
   the priors are `softmax(Δleaf(child, mover)/τ_p)` over children **from that node's
   mover's POV**, and the node value is `tanh(leaf(g, mover)/value_norm)`. This is the
   opponent's *policy* at opponent nodes.
3. **`Searcher::simulate`**'s backup (line ~941):

   ```rust
   n.w += if n.player_to_move == leaf_player { leaf_value } else { -leaf_value };
   ```

   The search assumes strict antisymmetry `V(s,p) = −V(s,1−p)`. **This is the constraint
   that ranks the options below**: any intervention that changes the *value* at
   opponent-mover nodes makes the sign-flip incoherent — the champion's own estimate of a
   position becomes minus a *different* function's estimate of it. The owner has already
   ruled on exactly this once, on the static surface (surface-A row: *"the leaf contract
   `V(s,p) = −V(s,1−p)` is what the search assumes"*), and `CL-082` measured the
   own-side-only (antisymmetry-breaking) open-city leaf at **−176.10 elo**.

### 2.2 The seam that already exists

`SearchConfig::jrules_prior_scope: JrPriorScope` (line 152) with

```rust
pub enum JrPriorScope { All, Own }
```

and the gate, verbatim (line ~635):

```rust
let jr_on = self.cfg.jrules_prior_dose != 0.0
    && match self.cfg.jrules_prior_scope {
        JrPriorScope::All => true,
        JrPriorScope::Own => self.root_player == Some(mover),
    };
```

`self.root_player` is latched per `search()` call (line 960) — *"Only `JrPriorScope::Own`
reads it"* — and `search()` is the entry point every PIMC world uses, so the latch is the
agent's own seat in every determinization. **`Opp` is one arm of that `match`:**
`JrPriorScope::Opp => self.root_player != Some(mover)`.

⚠️ **The clean consequence, and it is a design fact not a guess:** the enum's own unit test
`jrules_prior_scope_own_still_boosts_the_root` (line ~1423) records that *"The ROOT
expansion is `mover == root_player` under both scopes: identical."* Therefore under
`Opp` the **root expansion is byte-identical to the champion's** and *every* behavioural
difference is search-mediated, arriving through interior opponent nodes only. That is
exactly the estimand S1 wants — and it breaks the existing liveness control (§9.2).

### 2.3 Plumbing that already exists end-to-end

`scope` is threaded, with a string on each boundary:

| layer | file | site |
|---|---|---|
| rust enum + gate | `rust/carc/carc-core/src/search/mod.rs` | 88-101, 152, 258, 635 |
| pyo3 in/out | `rust/carc/carc-py/src/lib.rs` | 1556, 1586, 1622-1628, 1735, 1760-1762, 1841 |
| python config (carrier only) | `src/carcassonne_ai/heuristic_prior_mcts.py` | 218, 282-284, 358 |
| python→rust forward | `src/carcassonne_ai/rust_agent.py` | 266 |
| eval CLI | `scripts/classical_search/eval_fair_puct.py` | 3468, 4042 |
| calibration instrument | `scripts/classical_search/jrules_priors_e4_replay.py` | 498 |
| bench harness | `rust/carc/carc-core/examples/jp_bench.rs` | 41-52 |

**Seven files, all single-line string/enum sites.** That is the whole of option (i-a)'s
plumbing. Nothing else in the program needs to know.

---

## 3. THE INJECTION OPTIONS, RANKED

Ranked by **build cost × mechanism fidelity**. "Fidelity" means: does it change *which
opponent futures the search visits* without corrupting *the currency the champion prices
them in*?

### ⭐ (i-a) `jrules_prior_scope = "opp"` — the anchor's rules as opponent-node priors — **RECOMMENDED**

* **What it does.** At every expansion where the champion is *not* to move, each legal
  child's `Δleaf` gets `dose · T(child)` added before the prior softmax, where `T` is
  `leaf::jrules_prior_term` — the bot's J1/J2/J5/J6/J8 bundle **including the restored
  "he must already be there" JOIN predicates** (J1 / J2-steal / J6-road-join) that the
  static surface A had to drop as self-cancelling. **The J2-steal join predicate is
  literally the invasion predicate**: merge a stub onto a feature the other player holds.
  The value backed up is the unmodified champion's on every path.
* **Fidelity: high on surface, medium on content.** Surface is exactly right (opponent
  *policy* moves; champion *evaluation* does not). Content is the anchor's whole bundle,
  not invasion specifically — mask 31 also boosts open-city share (J1), unclaimed-feature
  value (J5), road/anchor policy (J6) and pivotal overcommit (J8) at opponent nodes.
  A `mask = J2`-only variant is more faithful but is a **new calibration and a fresh
  multiple comparison** (surface B's binding scope says so explicitly); §11 Q2 puts it to
  the owner.
* **Build:** the enum arm + 3 string sites + CLI choices + **a new interior positive
  control** (§9.2) + rust unit tests + a `--cand-jrules-prior-scope opp` smoke.
  **≈1 agent-day, 0 compute.** No leaf hash moves; the *inverted* hash gate (cand leaf hash
  must **equal** `a36d2e15a3b3d71d`) applies unchanged.
* **Cost at runtime:** ≈**1.085×** the candidate's search (inferred; §SIZING 3) — under the
  house `N4` 1.20 trigger with room.
* **Weakness, stated:** it is the complement of a measured null (§4).

### (i-b) invasion-shape priors at opponent nodes — the mechanism-faithful hybrid

* **What it does.** Same injection point and same "priors only, value untouched"
  discipline, but the boost term is `invasion::shape_a_term` / `shape_b_term`
  (`rust/carc/carc-core/src/leaf/invasion.rs`, 964 lines, already built, already
  dose-explored over β ∈ [0.02, 0.36]) instead of the J bundle. i.e. **the modelled
  opponent goes looking for the steal**, and nothing else changes.
* **Fidelity: highest of the four.** It is the one option whose *content* is invasion and
  whose *surface* leaves the currency alone.
* **Build:** a second boost function behind a second `SearchConfig` knob
  (`invasion_prior_dose` / `invasion_prior_scope`), reusing surface B's whole injection
  block; plus its own dose calibration (the invasion shapes are in *points*, so the J-term
  dose ladder does **not** transfer). **≈2–3 agent-days, 0 compute.**
* **Why it is not first:** it needs its own calibration and its own prereg, and the *only*
  thing that distinguishes it from (i-a) is content — so (i-a) answers the surface question
  first and at a third of the build. Name (i-b) as the licensed follow-on if (i-a)
  **expresses but does not pay**, which is precisely the state in which "wrong content on
  the right surface" becomes the leading explanation.

### (ii) asymmetric **leaf** at opponent nodes — an `opp_leaf: Option<LeafConfig>`

* **What it does.** `Searcher::leaf_at` (line 522) already takes `player` and
  `evaluate` already knows `mover` and `root_player`, so the call site *does* know
  to-move: `if mover != root_player { &cfg.opp_leaf } else { &cfg.leaf }` is mechanically
  a few lines. Dosing an invasion shape there makes the modelled opponent both *evaluate*
  and *order* through an invasion-aware lens.
* ⛔ **Fidelity: structurally compromised, and the program has already paid for this
  lesson.** The backup at line ~941 negates the leaf value across the player boundary. With
  two different leaves the champion's own value for a position becomes *minus a different
  function's* value, i.e. the search is no longer optimising anything coherent, and the
  distortion is **parity-dependent** (a line ending at an own-mover node and the same line
  one ply longer are priced in different currencies). This is the same antisymmetry break
  the owner ruled on for surface A, and `CL-082` measured its leaf-side cousin (own-side-only
  open-city) at **−176.10 elo / z −17.3**, cost-neutral. That is not proof S1-by-leaf would
  lose, but it is the strongest measured prior in the neighbourhood and it points one way.
* **Build:** a second `LeafConfig` in `SearchConfig` drags the whole leaf-hash dialect
  machinery, `leaf_config_rs`, `--cand-leaf-json`'s parser/guard, reconcile, the manifest
  provenance block and every wiring gate that currently assumes *one* leaf per side.
  **≈3–5 agent-days.**
* **Verdict: do not fund now.** Keep it named as the escalation if (i-a) and (i-b) both
  express and neither pays — i.e. only if "priors are too weak a lever at 22016 sims"
  becomes the surviving explanation. It would then need its own prereg arguing the
  antisymmetry break.

### (iii) S0v2 fire logic as an opponent-node policy (python script → rust port)

* **What it is.** `measurement/s0v2_scripted_prep/s0v2_agent.py`, 1,254 lines:
  `Structure` (a per-state feature index over `flat_leaf.decompose`), `victim_rank`,
  `merge_plausible`, `invasion_events`, and a **`PlanLedger`** carrying open plans
  across plies (SETUP → FOOTHOLD → MERGE → MAJORITY → HOLD).
* ⛔ **Two blockers, either sufficient.** (1) **The plan ledger is path-state**, and a
  search node is a *state*, not a path — the fire logic would have to be re-derived as a
  stateless per-node predicate, which is a redesign, not a port. (2) **The thing being
  ported is parked at its own ceiling**: three rounds, no arm S0v2-VALID, and the park
  diagnosis is that the missing half is *invasion QUALITY — EV-based victim selection —
  which needs search, not a rule*. Porting a rule that failed because it is a rule, into a
  search, to make the search behave like the rule, is circular.
* **Build:** ≈2–3 agent-weeks with a redesign in the middle. **Rank: last. Do not fund.**
* ⭐ **What S0v2 *should* be reused for is its harness, not its logic** — `s0v2_smoke.py`
  writes E4-schema archives and `stage_a_census.py` grades them. That is G2 (§6.3).

### Ranking table

| option | surface | currency intact? | build | runtime | mechanism fidelity | rank |
|---|---|---|---:|---:|---|:--:|
| **(i-a)** J-prior `scope=opp` | search priors | ✅ | **~1 d** | 1.085× | medium (bundle, not invasion) | **1** |
| (i-b) invasion-shape prior at opp nodes | search priors | ✅ | ~2–3 d | ~1.05–1.1× (unbenched) | **high** | 2 |
| (ii) `opp_leaf` asymmetric leaf | leaf value | ⛔ breaks antisymmetry | ~3–5 d | ~1.0× | high content, broken frame | 3 |
| (iii) S0v2 port | node policy | ✅ | ~2–3 wk + redesign | unknown | parked mechanism | 4 |

---

## 4. WHY THIS IS NOT A RE-RUN OF THE SURFACE-B NULL — AND THE HONEST ARITHMETIC

The distinction must be load-bearing or S1 does not deserve funding. Here it is, stated
against ourselves first.

**What was measured.** `jpriors_d0p5_deploy_fixed_v1_vs_champ11008_n800_b130e9`
(2026-08-14): dose 0.5, mask 31, **scope `all`**, both arms fair PIMC k8×1376 = 11008,
n=800 deck-paired, band 1.30e11 (retired, decision-influenced):
**margin −0.0175 pts/deck (sem 0.6214), z −0.0282, elo −3.04 ± 24.57 (2σ)**, `ms_ratio`
1.1751 (`N4` did not fire ⇒ **clean** null, not budget-confounded). Branch `N3 NO
CONVICTION`; no claim minted.

**What `all` contains.** Per the enum's own doc: *"Every expanded node, from that node's
MOVER's own POV"* — i.e. **own-nodes plus opponent-nodes**. `scope=own` is named in the
same row as *"UNTOUCHED BY EVERY BRANCH … a different hypothesis — opponent modelling —
needing its own prereg and band"*. **`opp` is the third cell of that partition and does not
exist yet.**

**The arithmetic, done honestly.** If the two components are roughly additive, then

```
effect(all) = effect(own) + effect(opp) = −0.0175 ± 0.62
```

so `effect(opp) ≈ −effect(own)`. The program's measured record says `effect(own)` should be
**negative**: making the champion itself play the anchor's rules lost on the static surface
(−2.4912 pts/deck, budget-confounded), and own-side-only asymmetric leaf bonuses lost hard
(`CL-082` −176.10 elo). If `effect(own)` ≈ −1 pt/deck, then `effect(opp)` ≈ **+1 pt/deck**.

⭐ **Three consequences, all of which change the design:**

1. **Size for +1, not +2.** A single n=800 arm has 2σ MDE ≈ ±1.26 pts/deck (§SIZING 4) and
   would read a true +1.0 at z ≈ 1.6 — *inconclusive*. This is why §6.4 pre-registers a
   **dual primary** whose second leg is the `opp − own` contrast (expected ≈ 2× the
   component) and why the branch map has a top-up arm.
2. **The `own` arm is not optional.** Without it the decomposition is unmeasured and a null
   on `opp` alone cannot distinguish "no asymmetry effect" from "both components ≈ 0".
3. **The banked `all` cell cannot be differenced against anything here.** Different band,
   and `CL-068` prices cross-band contrasts at 1.8–2.2× over-dispersion. It is **context**,
   never a statistic. That is why §6.4 re-runs `all` **in-band** as a control arm — which
   also re-measures it at the **current** 22016 budget rather than the retired 11008.

**The one mechanism argument that is genuinely new — and it is an argument, not evidence.**
Surface B's own pre-registered failure mode was the **sims-washout** (`F4/Gate B`: prior
influence decays with search depth as Q converges; +82.8/z3.48 at sims 200 → +8.0/z0.34 at
sims 800 on the same nets). At the **root**, 22,016 sims overwhelm any prior. At **deep,
low-visit opponent nodes Q never converges**, so `P` keeps a permanent share of the PUCT
`U` term, and the boost compounds along a line because *every* opponent expansion on that
line is boosted. ⚠️ **But `scope=all` already contained the opponent nodes**, so this
argument does not by itself separate S1 from the measured null — it only explains why the
opp component might be non-zero. **The separation rests entirely on the own-component being
negative.** Say it that way in any readout.

---

## 5. THE RULER PROBLEM, CONFRONTED

### 5.1 `CL-083`'s falsifier names an object that does not exist

*"≥2 pts/game vs a **validated exploit-expressing opponent** without regressing vs
champion+Carcasum."* Inventory of every candidate, with the disqualifying fact:

| candidate | status | why it cannot serve |
|---|---|---|
| **S0v2 (scripted exploiter)** | ⛔ PARKED 2026-08-28 at the script ceiling | No arm is S0v2-VALID. Best arm S0V2-F: 0.900 deliberate invasions/game (bar 0.90, *exactly* on it, SEM 0.111) but **G-DAMAGE +2.25 pp against a +10 pp bar**, and −11.57 pts/deck vs CTRL (z −3.32). Round 3 pooled two-range denial uplift **−0.17 ± 1.04** (FM) / **−0.57 ± 1.00** (FMH): *it does not deny the champion more than the champion denies itself.* Mechanism: the vendored full-points-on-tie rule means a 1-v-1 invasion denies **zero**; S0v2 ties (took-all 9.3–14.0% vs owner 28.9%). **An opponent that denies nothing gives defence nothing to save.** |
| **shape-B "invader"** (`invasion_alpha 0.09 cap 11.0`, leaf `42adadc988784b44`) | ⛔ | Used as the r2/r3 C-ladder opponent, but the roadmap rider of 2026-08-30 records: ***"r2/r3 B-invader does not invade ⇒ the licensed powered-C confirmation is FROZEN until the C-ladder caveat is resolved."*** |
| **the owner (E4)** | ✅ real, ⛔ unusable as a verdict | Nonstationary (anchor **flipped** 2026-08-25), rules-epoch-conditional, phone-conditioned, and **arithmetically out of reach**: per-game margin sd ≈ 19–20 pts (measured, §5.3) ⇒ resolving a +2 pts/game change at 2σ needs n ≈ 800 **games he plays himself**. The corpus is 50. |
| **Carcasum @5000 ms** | ✅ usable, ⛔ wrong estimand | A genuine out-of-lineage reference (champion +4.08 pts/deck, z +4.175, n=400) — but it is not an *exploit-expressing* opponent, so it can only serve as a **non-regression guard**, which is exactly what `CL-083` also asks for. |

### 5.2 What I am **not** proposing

I am not proposing to build an exploiter to license S1. That work has been funded twice
(S0, S0v2), reached its ceiling, and the park diagnosis is that the missing half needs
*search*. Re-funding it as a dependency of S1 would make a one-day build wait behind a
multi-week open research problem.

### 5.3 What I propose instead — the two attainable judge-free tests

**(a) SIGNATURE — does S1 build a different board?** Necessary, not sufficient. Cheap,
already-tooled (`stage_a_census.py` + `s0_signature.py`), and — crucially — **it does not
require the opponent to punish**, because it measures what S1 *constructs*, not what it
*suffers*. Statistics, all read as **(S1-side − champion-side) on the same deck, averaged
over both seatings**, so the deck-range drift that killed S0v2's CTRL-relative gates
(CTRL denial spanned **5.1×** across four 60-game ranges) is **common-mode and cancels**:

| statistic | E4 owner | E4 champion | self-play CTRL @2752 (n=60) |
|---|---:|---:|---:|
| own big claims that end up contested | **4.3 %** | 39.1 % | 9.0 % |
| own farmer deployments scoring ZERO | **5.4 %** | 46.2 % | 15.05 % |
| games with own farms zeroed | 0 % | 18 % | 5.8 % |
| deliberate invasions initiated /game | 1.80 | 0.14 | 0.550 ± 0.060 |

Measured per-game dispersion on the CTRL arms (`smoke_ctrl*_signature.json`, 3 × 60 games,
computed for this document): deliberate invasions per side **mean 0.32–0.63, sd 0.53–0.71**;
farm points per side **mean ≈21.1, sd ≈10**; margin **sd 18.9–20.2**. At n=800 games the
deck-matched invasion-rate contrast has sem ≈ **0.023/game** and the farm-points contrast
sem ≈ **0.5 pts/game** — both an order of magnitude tighter than the margin. **The signature
is cheap to resolve; the margin is what is expensive.** ⚠️ And note the between-range drift
in those same three CTRL arms (0.633 / 0.517 / 0.317 invasions/game) — that is the S0v2
lesson, and it is why nothing here may be read CTRL-relative across ranges.

**(b) MARGIN — the self-anchored deploy-budget head-to-head** vs the unmodified champion,
22016 both sides, deck-paired, one band. This is the deployability question and it is the
one the house already knows how to run and adjudicate.

### 5.4 ⭐ The decomposition control is also the cheapest remaining shot at a ruler

The `scope=own` arm is the anchor's rules driving the champion's **own** play — a *soft*
version of exactly what S0v2 hard-scripted. If G2's census shows the `own` arm's deliberate
invasion rate and, critically, its **points-denied-to-the-opponent** (G-DENY — S0v2's
banked instrument lesson: *"G-DENY is the honest damage statistic"*) rise above the
deck-matched champion baseline, then **the control arm has produced the exploit-expressing
opponent** that the defence cell needs — for free, inside a cell we are running anyway.
Honest prior: **it probably will not** (a soft prior boost should express *less* than a
hard script, and the hard script reached only 0.900 invasions/game and denied nothing). But
it costs nothing extra to look, and it is the only route to `CL-083`'s falsifier that does
not start a new multi-week program.

### 5.5 The proposed amendment to `CL-083` (owner's call, §11 Q4)

> The falsifier's *"vs a validated exploit-expressing opponent"* clause is **retained but
> flagged unattainable at present**. A plan-level mechanism may be adjudicated on the
> two-part judge-free substitute — (a) a deck-matched structural signature moving in the
> owner's direction at ≥2σ **and** (b) a non-regressing self-anchored deploy-budget margin
> **and** (c) non-regression vs Carcasum — with the explicit rider that **this substitutes
> a weaker estimand**: it can establish that the champion now builds and defends
> differently, and it cannot establish that the difference is worth ≥2 pts/game against a
> human-class invader.

---

## 6. THE STAGED GATE SEQUENCE

⛔ Bars below are **proposed**. None is pre-registered until a `READ_RULE.md` is committed
before any statistic is read, per house rule (`CL-079`).

### 6.1 G0 — build and wiring (0 compute)

1. `JrPriorScope::Opp` + the one `match` arm (§2.2).
2. String sites: pyo3 in/out, python validator, CLI `choices`, `jp_bench`.
3. **The new positive control** (§9.2) — the existing one *cannot* serve.
4. Rust unit tests: dose-0-with-moved-scope **bit-identical**; `Opp` leaves **root priors
   identical** to the champion while moving **root visits**; `Opp` + `Own` boosts are
   disjoint and their union reproduces `All` on a pinned root.
5. `--cand-jrules-prior-scope opp` end-to-end smoke through `eval_fair_puct --smoke`.
6. F-c golden-digest re-hash + champion fingerprint recompute unchanged.

**Gate:** all of the above green, on a per-box rebuilt wheel. A stale wheel must fail
**loud** (the surface-B `TypeError` fail-closed pattern).

### 6.2 G1 — EXPRESSION (⭐ the kill gate; 0 games)

Instrument: `scripts/classical_search/jrules_priors_e4_replay.py` with an `opp`-scope arm
(one line, §2.3), over the banked E4 archives at the **current** deploy budget
(k16×1376 = 22016), which is what the champion actually plays. Precedent: surface B ran this
on 26 archives / **1,556 champion plies per rung**.

Two statistics, both pre-committed:

* **(E1) root pick-flip rate** — fraction of champion plies where the armed arm plays a
  different action. ⚠️ **This will be materially lower than surface B's 13.05 %**, because
  under `Opp` the root expansion is *identical* and every flip is search-mediated. The bar
  must be set for a search-mediated intervention **before** any rate is read.
* **(E2) mean root visit-distribution total-variation distance** vs the champion's pooled
  root. Graded, cannot be zero if the surface is live, and immune to the "the flip needed
  to cross an argmax boundary" quantisation that makes E1 lumpy.

**Proposed read rule** (FUND-SMALLEST family, the house pattern): dose ladder
{0.5, 1.0, 2.0} plus a pre-committed 0.25 rung; fund the **smallest** dose clearing
**E1 ≥ 5 %** *or* **E2 ≥ 0.05**; `NO-EXPRESSION` (neither cleared at the top rung) ⇒ **stop,
no cell, no band, and the recorded answer is "opponent-node priors do not survive 22,016
sims"** — which is a real, cheap, publishable result and closes the branch.

⚠️ A dose calibrated for `all` does **not** transfer: surface B's binding scope lists
"other dose rungs" as untouched, and `Opp` reaches a different node population.

### 6.3 G2 — SIGNATURE (rider on G3, 0 extra games)

**Build item:** add archive banking to `eval_fair_puct.py` (E4 schema:
`(deck_seed, actions, provenance)`), so any cell's games can be censused afterwards.
`s0v2_devplay.py` already writes exactly this schema and `stage_a_census.py` already grades
it (50/50 E4 games reconcile *exactly*), so the census side is free. ⚠️ Edit under
worktree isolation, merge at a quiet window (`feedback_worktree_isolation_live_tree`).

Read (deck-matched, both seatings, §5.3): the four exposure/expression statistics, plus
**G-DENY** (points denied to the opponent) for §5.4's ruler-construction check.

**Proposed bar (non-gating for adoption, gating for interpretation):** for the `opp` arm,
"own big claims that end up contested" and "own farmer deployments scoring ZERO" must fall
vs the deck-matched champion side at **≥2σ**. **Necessary, not sufficient** — a margin win
with a flat signature means the mechanism is *not* the stated one and the readout must say
so.

### 6.4 G3 — THE DECOMPOSITION CELL (the verdict)

One fresh band (**155e9 proposed, unclaimed** — 154e9 is the highest in
`governance/BAND_REGISTRY.csv`), **one shared deck set** (CRN across arms, which P2
requires), three arms, every arm deck-paired and seat-balanced against the **unmodified
champion**:

| arm | config | n (recommended) | role |
|---|---|---:|---|
| **OPP** | `jrules_prior_dose = d*`, mask 31, **scope `opp`** | 1,200 | **primary candidate** |
| **OWN** | same dose/mask, scope `own` | 1,200 | **decomposition control** (and §5.4's ruler probe) |
| **ALL** | same dose/mask, scope `all` | 800 | **in-band symmetric control** — the "just another dose" arm the design owes, re-measured at the current 22016 budget |

⚠️ **The n choice is argued in [`SIZING.md`](SIZING.md) §4.1 and it is the design's most
uncomfortable number**: at n=800 the primary reads a true +1 pt/deck (the size §4's own
decomposition arithmetic predicts) at only z ≈ 1.6. n=1,200 on the two gated arms buys
P1 2σ = ±1.03 and P2 z ≈ 2.75 against D = +2, for +115 worker-h. **Do not launch this cell
at n=800 without accepting that `S1-BOUNDED-NULL` is then the modal outcome even if the
effect is real.**

Instrument, both sides identically: fair PIMC **k16×1376 = 22016** (`PRODUCTION.yaml`
`fair_deploy`), rust backend, `fixed_v1` + R9, exact-K 2 marginalized, c_puct 1.5 / τ_p 5 /
float / visits, **tie-arbiter OFF both sides**. ⚠️ Arbiter-off is a deliberate deviation
from the deployed desktop champion (`tiearb.enabled: true, B: 64`) with three reasons:
(1) it is the precedent the champion's **own** budget promotion was measured under
(`h2h_22016_20260824`: *"The arbiter is verifiably OFF on both sides"*); (2) the arbiter
overrides the search's pick at exactly the plies where it fires, **diluting** a search
intervention; (3) cost. **Deploy transfer is therefore an assumption and must be stated in
the readout, not buried.**

**Dual primary, Holm-corrected (the `c1_pricing_prep` precedent):**

* **P1 — deployability.** `margin(OPP vs champion)`, deck-paired pts/deck.
* **P2 — asymmetry.** `D = margin(OPP) − margin(OWN)`, deck-paired on the **shared** deck
  set (the `tiearb_widening` `WIDE − NARROW` precedent, which used exactly this statistic
  as its primary).

**Proposed branch map** (to be frozen in `READ_RULE.md` before game 1):

| branch | condition | consequence |
|---|---|---|
| `S1-FIRES` | P1 ≥ +2σ **and** G2 signature bar met | licence a confirm at n ≥ 1600 + the G4 guards; **no adoption on a screen** |
| `S1-ASYMMETRY-ONLY` | P2 ≥ +2σ, P1 not | the decomposition is real, the deployable half is not; report, fund (i-b) or a top-up, **do not adopt** |
| `S1-BOUNDED-NULL` | \|P1\| and \|P2\| < 2σ | record the bound (±1.03 pts/deck at n=1,200; ±1.26 at n=800); branch closes; re-open needs a **mechanism** argument, not more n |
| `S1-NEGATIVE` | P1 ≤ −2σ | opponent-node modelling is harmful at this dose; closes with the CL-080/082 family |
| `N4-COST` | `ms_ratio_cand_over_opp` > 1.20 | first-block abort option (predicted 1.078, §SIZING 3) |
| `N5-FAIL` | any failed game / stranded claim | void and re-read per IS-A1 precedent |

Standard 13-gate wiring set applies, **with the hash gate INVERTED** (candidate
`cand_leaf_hash` must **equal** `a36d2e15a3b3d71d`; a moved hash is the defect), plus the
resolved `cand_jrules_prior.{dose,mask,scope}` in every manifest and the §9.2 positive
control captured before game 1 on **every** box.

### 6.5 G4 — guards (conditional on `S1-FIRES` only)

* **Carcasum @5000 ms**, n=400, fresh band, arbiter off — does S1 keep the champion's
  +4.08 pts/deck (z +4.175)? This is `CL-083`'s own "without regressing vs
  champion+Carcasum" clause, and it is the only out-of-lineage leg available.
* Non-regression vs the champion is P1 itself.

### 6.6 G5 — E4

Owner plays S1. **Corroboration only.** §5.1 shows E4 cannot verdict a 2 pt/game change
(n ≈ 800 games needed). Do not promise otherwise.

### 6.7 What I deliberately do **not** propose

A **2752 screen**. It is cheap (~21 worker-h) but its kill power is *inverted* for this
mechanism: an opponent model needs tree depth to express, so a null at 2752 does not kill
and a hit at 2752 does not transfer (`CL-079`: a 2750 screen is not a verdict). G1 is the
cheap kill gate; buy it instead.

---

## 7. KILL-SET CHECK — WHY S1 IS NOT A RE-LITIGATION

Swept `docs/LEVER_INDEX.md` for every adjacent row. **The asymmetry — opponent-nodes-only —
must be load-bearing in every line of this table, and where it is not, I say so.**

| adjacent row | what it measured | why S1 differs | honest residual risk |
|---|---|---|---|
| **J-rules on search (surface A)** — static leaf terms, antisymmetric | deploy cell, n=800, **−2.4912 pts/deck, z −3.86, −33.98 elo**; `N4` fired (`ms_ratio` 1.2116) ⇒ *loss confounded by budget* | S1 moves **priors**, not the leaf; **no leaf hash moves**; cost 1.085× vs the 1.2116 that confounded A | the *content* (the J bundle) is shared, so a content-level failure would hit both |
| **J-rules as policy priors (surface B), `scope=all`** | deploy cell, n=800, **−0.0175 pts/deck, z −0.0282**, clean null (`N4` did not fire) | ⭐ **THE load-bearing row.** `all` = own+opp; S1 = **opp alone**. The row itself lists `scope=own` as *"UNTOUCHED BY EVERY BRANCH … a different hypothesis — opponent modelling"* | ⚠️ **This null caps the SUM.** S1 is live only if the components are opposite-signed (§4). Stated up front, not discovered later. |
| **J-rules as ROOT FILTERS (surface C)** | `NO-EXPRESSION`: exclusion 2.80–7.76 %, every mask under the 10 % bar | S1 is not a filter and removes no action | ⚠️ Its recorded answer — *the champion at deploy depth already plays inside the anchor's hard rules on ~93 % of decisions* — is a real prior that **expression will be low**. G1 exists because of this row. |
| **invasion-risk term family, shapes A–D** (3 screen rounds, n=2800/2800/3200 at 2752) | **zero 2σ cells.** A flat-null on its own fine ladder (−0.38/−0.28/−0.22, \|z\|<0.7); B in the noise column; only solid A fact is β 0.36 overdose harm (z −5.8); C quasi-replicates (+0.91 z1.49 / +1.00 z1.63 on two bands) | S1 is **not a leaf dose**: no score is added anywhere, the currency is untouched, and the surface is opponent *policy* | ⚠️ The C signal was measured **against the shape-B "invader" that does not invade** (roadmap rider) — so the family's one repeated signal rests on a compromised instrument. Do not cite C in S1's favour. |
| **C2 — adversarial tie valuation** | **dropped 2026-08-28** by the advisor as a member of the measured-harmful family | S1 adds no score and changes no tie valuation | none |
| **targeted denial / `opp_bonus_cap` / open-city** (`CL-080`, `CL-082`) | unconditional/static leaf bonuses; **every calibrated, fundable form harmful at deploy**; ⚠️ the **own-side-only ASYMMETRIC** open-city form read **−176.10 elo, z −17.34, cost-neutral** | S1's asymmetry is in the **search's opponent policy**, not in the leaf; it never breaks `V(s,p) = −V(s,1−p)` | ⭐ **This is the sharpest warning in the table and it is why option (ii) is ranked third.** Asymmetry *in the leaf* is measured catastrophic. |
| **C1 — rollout re-ranking at contested plies** | `C1-NULL-BOUNDED` judge-free: contested +1.07 ± 0.70, farm_capture +2.41 ± 1.84 (n=14 cap); winner's curse **+6.54 ± 0.41 (z 16)** = `CL-084` | S1 is inside the search, not a post-hoc per-ply re-pick; it selects nothing on the data it is graded on | ⚠️ `CL-084` binds S1 too: **no selecting-then-reporting.** The band, doses, arms and branch map freeze before game 1. |
| **S0 / S0v2 — the exploit-expressing ruler** | 3 rounds, parked at the script ceiling; no S0v2-VALID arm | S1's gates (§6) do **not** depend on it — that is the whole of §5 | ⚠️ The price is a **weaker estimand**, stated in §5.5. |
| **arbiter playout-policy upgrade** ("change the opponent in the playouts") | queried and **near-dead**: F = 0.811 CI95 [0.450, 1.320]; the v2.9-greedy leg read F₂.₉ = 0.7355, *worse* | different surface entirely: the arbiter fires **post-search, at exact ties, at the root**; S1 changes interior search | none — but it is why the G3 cells run **arbiter off** (§6.4) |
| **prior-as-move-ordering / depth transfer (F4/Gate B)** | prior influence **decays with search depth** (the sims-washout mechanism) | S1 boosts **low-visit interior** nodes where Q never converges, and compounds along a line | ⚠️ argument, not evidence — and `scope=all` already contained those nodes (§4) |
| **within-turn tree carry / tree reuse / k-width / adaptive-k** | search-efficiency levers, unrelated object | S1 changes *what is searched*, not how much | none |

**The symmetric control the design owes** (§6.4 arm ALL) is explicitly the "is this just
another dose?" arm. Its prior is the banked surface-B null — and re-running it **in-band at
22016** is the only way to make the `opp` / `own` / `all` decomposition a statistic rather
than a cross-band anecdote (`CL-068`).

---

## 8. COST

Full arithmetic in [`SIZING.md`](SIZING.md). Headline, from two **realized** cost anchors
(`h2h_22016_20260824` = 382 worker-s/game at 22016-vs-11008; `invasion_screen_r3` = 96.2
worker-s/game at 2752-vs-2752):

| item | games | worker-h | two-box wall (local W30 + laptop W22) |
|---|---:|---:|---:|
| G0 build (+ `jp_bench` cost check) | 0 | ~0 | ~1 agent-day |
| G1 expression, champion + 4 dose rungs | 0 | ~13 | ~15 min |
| pre-flight smoke (owed, §SIZING 2) | 20 | 1.5 | ~6 min |
| **G3, OPP 1200 + OWN 1200 + ALL 800 @ 22016** | 3,200 | **~459** | **~9.2 h** |
| *(cheaper variant: three arms × n=800)* | *2,400* | *~344* | *~6.9 h* |
| G2 census (rider) | 0 | ~0.2 | minutes |
| G4 Carcasum guard (conditional) | 400 | ~40 | ~0.8 h |
| optional confirm at n=1600 (`S1-FIRES`) | +1,600 | ~229 | ~4.6 h |

⚠️ The 496 worker-s/game figure for 22016-both-sides is a **two-point linear extrapolation**
(§SIZING 2). House rule is *bench, then extrapolate, then commit* — a 20-game smoke at
production knobs is **owed before launch** and is ~1.5 worker-h.

---

## 9. BUILD ITEMS AND WIRING GATES

### 9.1 Code (option i-a) — every site, so the build brief is complete

| # | file | change |
|---|---|---|
| 1 | `rust/carc/carc-core/src/search/mod.rs` | `enum JrPriorScope { All, Own, Opp }` + doc; `JrPriorScope::Opp => self.root_player != Some(mover)` in the line-635 `match` |
| 2 | `rust/carc/carc-py/src/lib.rs` | `"opp"` in the 1622 parse `match`; `Opp => "opp"` in the 1760 render `match`; error string |
| 3 | `src/carcassonne_ai/heuristic_prior_mcts.py` | `("all", "own", "opp")` in the line-282 validator |
| 4 | `scripts/classical_search/eval_fair_puct.py` | `choices=("all","own","opp")` at 3468 + help text |
| 5 | `scripts/classical_search/jrules_priors_e4_replay.py` | an `opp` arm in `_make_arms`; **swap the positive control** (§9.2) |
| 6 | `rust/carc/carc-core/examples/jp_bench.rs` | `Some("opp") => …` — gives the cost measurement for §SIZING 3 |
| 7 | `tests/test_jrules_priors.py` + rust unit tests | §6.1 items 4 |
| 8 | `scripts/classical_search/eval_fair_puct.py` | **archive banking** for G2 (separate, reusable) |

⚠️ Build in a **git worktree** with `PYTHONPATH` override and merge at a quiet window; the
`carc_rs` wheel must be rebuilt **per box** and a stale wheel must fail loud
(`feedback_worktree_isolation_live_tree`, surface-B `TypeError` precedent).

### 9.2 ⭐ The existing positive control does not work for `scope=opp` — this is a real trap

`jrules_priors_e4_replay._assert_surface_b_live` asserts, on a pinned 30-ply midgame root
at 32 sims, that **`root_priors` move** between dose 0 and dose 1.0. Under `Opp` the root
expansion is `mover == root_player`, so the boost is **off at the root by design** and
`root_priors` are **identical** — the control would fail on a *correctly working* build,
and (worse) a naive "fix" that made it pass would mean the scope gate was mis-wired.

**Proposed replacement, two-sided, on the same pinned root:**

* **must NOT move:** `root_priors` and `root_leaf_value_bits` (dose 0 vs dose 1.0 @ `opp`)
  — a moved root prior under `opp` is the defect;
* **must move:** the root **visit distribution** (`root_children` `N`) at a sim count high
  enough to reach interior opponent nodes (≥ 256 sims on that root);
* plus the union identity: on the same root, the set of expansions boosted under `Own` and
  under `Opp` is disjoint and their union equals `All`'s.

Without this, `scope=opp` is exactly the failure class this house has been burned by:
a silently-inert knob grading a perfect champion-vs-champion null.

---

## 10. SCOPE AND FORBIDDEN READINGS (proposed, binding if funded)

1. This design prices **one encoding at one dose** — the frozen `joshua_bot.PRESETS["current"]`
   J bundle at mask 31 — applied at opponent nodes. It is **not** "the anchor's strategy",
   **not** the owner's play, and **not** invasion pricing in general.
2. **No contrast with the banked `all` cell is a statistic** (different band; `CL-068`).
   The in-band ALL arm is the only differenceable control.
3. `|z| < 2` is **never** "refuted". *Killed / dead / does nothing* are forbidden readings
   of a bounded null; quote the bound.
4. A margin result with a **flat G2 signature** does not license the mechanism story, only
   the number.
5. Arbiter-off ⇒ **deploy transfer is an assumption**, stated in the readout.
6. Nothing here licenses a `PRODUCTION.yaml` change. A screen aims; it does not verdict.
7. `CL-084` binds: doses, arms, band, deck ranges and the branch map freeze **before**
   game 1, and the selecting observation is never pooled with the confirming one.

---

## 11. OPEN QUESTIONS FOR THE OWNER

**Q1 — Fund the recommendation as scoped?** ~1 agent-day build + ~474 worker-h (≈9.5 h
two-box) to a verdict, no band spent until G1 clears. Yes / trim to the ~359 worker-h
n=800 sizing / no.

**Q2 — mask 31 (the frozen bundle) or a J2-steal-only mask?** Mask 31 is comparable with
the banked `all` cell and needs no new content decision; **J2-only is more faithful to
"invasion-capable"** but is a fresh calibration and a fresh multiple comparison. My
recommendation: **mask 31 first** (surface question before content question), with J2-only
named as the licensed follow-on. This is a genuine fork and it is your call.

**Q3 — three arms or two?** Dropping the in-band `ALL` control saves ~115 worker-h (~2.3 h)
but makes the decomposition uncheckable and leaves the only symmetric comparison
cross-band (`CL-068` forbids differencing it). My recommendation: **keep all three.**

**Q4 — amend `CL-083`'s falsifier (§5.5)?** The *"validated exploit-expressing opponent"*
clause currently makes the claim unfalsifiable by any funded route. I propose flagging it
unattainable and adjudicating plan-level mechanisms on the judge-free substitute, with the
weaker-estimand rider written into the claim. Governance change, your call.

**Q5 — arbiter off (recommended) or on?** Off = precedent + no dilution + cheaper; on =
deploy fidelity at ~+17 % cost post-tier1-swap and a re-owed IDENT.

**Q6 — if G1 reads `NO-EXPRESSION`, stop or escalate to option (i-b)?** My recommendation:
**stop and record it.** "Opponent-node priors do not survive 22,016 sims" is a clean,
cheap, reusable result, and (i-b) shares the surface whose expression just failed.

---

## 12. WHAT WOULD CHANGE MY RECOMMENDATION

* If the owner wants the **mechanism** rather than the **decomposition**, option **(i-b)**
  is the right build and the extra 1–2 agent-days is well spent — S1 would then be "the
  modelled opponent hunts the steal", which is a cleaner sentence than "the modelled
  opponent plays the anchor's bundle".
* If G1's expression comes back **strong** (E1 ≥ 15 %), the sims-washout story is dead for
  this surface and the cell is worth n = 1600 from the start.
* If anyone builds a **denying** exploiter (took-all conversion, not tie conversion), the
  whole §5 apparatus is replaced by `CL-083`'s original falsifier and S1 should be
  re-graded against it.
