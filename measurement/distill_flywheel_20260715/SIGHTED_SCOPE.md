# SIGHTED representation scope — fair-champion distillation flywheel (2026-07-16)

**STATUS: SCOPING DOC (read-only investigation). No code changed, running job untouched.**

Question: the stage-1 fair-distillation flywheel (iters 0–3, RUNNING) uses a **non-sighted** net
(78ch / 10-scalar) to match `checkpoints/warmstart_canonical.pt`. Should we instead distill onto the
**sighted** (bag-aware) representation (81ch / 42-scalar)? Is that even sound (fair-safe), and what does
the switch take?

---

## 0. TL;DR / RECOMMENDATION

- **Sighted is FAIR-SAFE.** The two things it adds are (a) 3 farm-connectivity planes derived from the
  *visible board's placed meeples*, and (b) a 32-dim **bag histogram** = an **order-agnostic multiset**
  count of the remaining deck (÷ full-deck count). Neither encodes deck ORDER, next-N tiles, or any
  future draw. This is exactly the PUBLIC bag information the fair PIMC champion itself reasons over. No
  clairvoyant leak → no strategy-fusion reintroduced. Code evidence in §1. **This is the gate, and it passes.**
- **The switch is purely an input-representation change.** The champion plays byte-identically regardless
  of the encoder (the agent decides on the raw referee `board`, the encoder only *records* the observation
  — `gen_fair_distill.py:175` vs `:188`). So the recorded policy/value TARGETS are unchanged; only the net's
  input X goes 78ch→81ch. Sighted just gives the net more public features to fit the same fair targets.
- **A clean sighted warm-from ALREADY EXISTS → Path A (same-day).**
  `/mnt/c/carc-shared/m2_sighted/warmstart_sighted.pt` (+ `.best.pt`) is an **arch-confirmed 81ch/42,
  sighted=True, 96×6 full AZ net** — a fresh **heuristic warmstart** (no self-play / residual / deck
  baggage), trained from `data/warmstart/heuristic_tau05_sighted`, i.e. the **exact sighted twin of
  `warmstart_canonical.pt`**. It drops straight into the flywheel as iter-0 warm-from. No warmstart training
  run needed. (Fallback Path B — `train_warmstart.py --sighted` on the on-disk `heuristic_tau05_sighted`
  dataset — remains available if we ever want a fresh one.)
- **train_iter.py needs NO code change** — it already reads `sighted`/`n_input_channels`/`n_scalar_features`
  from the warm-from checkpoint and builds the net accordingly (`:473–482`, propagates at `:767–770`).
- **Every stage fails LOUD on a channel mismatch** (conv shape error at first forward) — there is no silent
  mis-train path. The risk is a crash-on-launch, not corrupted data.
- **Recommendation: sound (fair-safe) and cheap — but temper the payoff.** Sighted is the more faithful
  *fair* representation (net sees the same public bag the teacher marginalizes over) and is low-risk. Because
  the clean warm-from already exists, cost ≈ **~1 h operator+GPU** (probe regen + config flip + smoke +
  relaunch), discarding the 2–3 non-sighted iters already computed. **Caveat (cost-discipline):** the
  sighted rep's *VALUE* head has already been falsified 8× — the M2 sighted-AZ value route (CL-039/042,
  "M2 KILL") and both C-cheap deck-aware value heads (CL-049 W0/L100, CL-050 +9.2 elo null) all found the
  sighted value inert vs the v2.9 leaf. That does **not** condemn sighted here (this flywheel *severs* the
  value loop — the frozen champion leaf is the only value; the net contributes POLICY priors only), but it
  means the expected win is **policy fidelity + a bag-aware value SUBSTRATE for a deployable iter-12**, NOT a
  suddenly-strong value head. Cleanest call: let non-sighted stage-1 finish (nearly done) and run sighted as
  a clean A/B — the frozen probe (policy CE / top-1 / value_r) is directly comparable and directly tests the
  CL-033 "is the net inert because it's bag-blind?" hypothesis for the price of one extra stage-1.

Effort fork verdict: **Path A (same-day)** — a clean, arch-confirmed sighted warmstart checkpoint already
exists (`/mnt/c/carc-shared/m2_sighted/warmstart_sighted.pt`); no warmstart training run is needed. See §2.

---

## 1. GATING FINDING — is sighted fair-safe or leaky? (with code evidence)

The sighted rep is defined in **`src/carcassonne_ai/sighted_planes.py`** and gated in
**`src/carcassonne_ai/game_wrapper.py`** behind `Game(sighted=True)` (default OFF).

Constants (verified): `board_repr.py:107 N_CHANNELS=78`; `features.py:38 N_SCALAR_FEATURES=10`,
`:39 N_FARM_SCALARS=2`; `sighted_planes.py:80 N_BAG=32`, `:89 N_FARM_PLANES=3`.
So sighted = 78+3 = **81 channels**, 10+32 = **42 scalars** (with `include_farm_scalars=False`; note 42
confirms farm-scalars OFF — 10+2+32 would be 44). Matches the task's "81ch/42".

Where sighted is applied — `game_wrapper.py:589–602` (`get_canonical_form`):
```
if self.sighted:
    from .sighted_planes import bag_histogram, farm_connectivity_planes
    fp = farm_connectivity_planes(board.state, player, board.offset, board.offset.size)
    arr = np.concatenate([arr, fp], axis=0)                 # 78 -> 81 ch
    scalars = np.concatenate([scalars, bag_histogram(board.state)])  # 10 -> 42
```
The first 78 channels / 10 scalars are byte-identical to the blind path (comment `:592–596`).

### Extra feature 1 — 3 farm-connectivity planes (`sighted_planes.py:138–173`)
Per-cell live farm ownership (`plane0=root owns`, `plane1=opp owns`, `plane2=contested`), computed from
`decompose(state)` over the **currently placed meeples** (`_farm_component_owners`, `:95–135`, iterates
`state.placed_meeples`). This is a pure function of the **visible board** — who has farmers where, and which
field each tile-cell touches. Both players see the board. **PUBLIC → fair-safe.** No deck/bag/order content.

### Extra feature 2 — 32-dim bag histogram (`sighted_planes.py:176–194`) — THE ONE THAT MATTERS
```
def bag_histogram(state) -> np.ndarray:
    counts = np.zeros(N_BAG, dtype=np.float32)
    for t in state.deck:                                    # remaining undrawn tiles
        i = _BAG_INDEX.get(getattr(t, "description", None)) # keyed by TILE TYPE, not position
        if i is not None:
            counts[i] += 1.0
    nt = getattr(state, "next_tile", None)
    if nt is not None and state.phase == GamePhase.TILES:    # the tile the mover already drew (public to them)
        i = _BAG_INDEX.get(getattr(nt, "description", None))
        if i is not None:
            counts[i] += 1.0
    return counts / _BAG_MAX                                 # ÷ full-deck count -> [0,1]
```
**Why this is fair-safe, rigorously:**
- It reduces `state.deck` (an ordered list) to a **count vector over the 32 distinct tile TYPES** — the
  loop only increments a per-type bucket. **Deck ORDER is destroyed.** No feature says "the next tile is X"
  or "tile at deck[k]"; there is no positional indexing anywhere in the module.
- It is the remaining-tile **multiset**, which is **public**: both players know the fixed 72-tile base
  multiset (frozen at `:45–87`) and can see everything played, so both know exactly what remains as a bag.
  This is the *same* public information `FairHeuristicPriorAgent` marginalizes over via determinization.
- `next_tile` is included only in the TILES phase — it is the tile the current mover has **already drawn**
  and is about to place, i.e. already revealed to the decision-maker. Not future info.
- The module docstring states it outright (`:24–28`): "Both are STRUCTURAL: they are functions of the
  board / bag, NOT of the oracle_q / leaf_q labels ... the production ... path never imports this module."

**Contrast with the leak we pivoted away from:** clairvoyant strategy-fusion comes from distilling a teacher
that sees the deck **order** (which specific tile comes next). Sighted exposes only the **unordered bag** —
legitimate blind strategy (e.g. "3 straight-roads remain, this gap is likely fillable"), which a strong
human also reasons about. **Verdict: FAIR-SAFE. A single order-aware feature would kill it; there is none.**

Corroborating: `DESIGN.md:25` already verified the *non-sighted* rep is public-info-only ("no
deck-order/future-draw information ... clairvoyance lives in the search stepping the true deck, not the
encoding"). Sighted adds only the order-agnostic bag + board-derived farm planes, so it stays public-only.

### Teacher-play decoupling (why targets are identical)
`gen_fair_distill.py`: `obs, scl = encoder.get_canonical_form(board, mover)` (`:175`) only records; the move
is `action = agent.move(board)` (`:188`) on the **raw referee board**. The champion never consumes the
sighted features — it plays blind PIMC either way. So the policy (pooled visits) and value (backfilled
score_diff) TARGETS are byte-identical under sighted vs non-sighted; only the net's input X changes.

---

## 2. Sighted warm-from inventory + which effort fork applies

**Existing 78ch (non-sighted) checkpoints** (NOT usable as sighted warm-from):
- `checkpoints/warmstart_canonical.pt` — first conv `(96,78,3,3)`; keys: `n_filters=96, n_blocks=6,
  data_root=data/warmstart/heuristic_tau05`. **Notably it does NOT carry `n_input_channels`/`sighted` keys**
  — train_iter relies on its defaults (78 / False). This is exactly why the current run is non-sighted.
- `checkpoints/warmstart_canonical_192x14.{pt,best.pt}` — a larger 192×14 arch, non-sighted, wrong arch anyway.

**Sighted (81ch/42) CHECKPOINTS that DO exist** (all arch-confirmed by loading `stem.0.weight` =
`(96,81,3,3)`, `n_scalar_features=42`, `sighted=True`, `value_global_pool=True`, 96×6). Three families, all
under `/mnt/c/carc-shared/`:

| Checkpoint | Value target | Clean warm-from? | Verdict / status |
|---|---|---|---|
| **`m2_sighted/warmstart_sighted.pt`** (+ `.best.pt`) | fresh heuristic warmstart (absolute) | **YES — cleanest** | Full AZ net (policy+value+ownership aux w0.15). No self-play/residual/deck baggage. Trained from `heuristic_tau05_sighted`. **← use this.** |
| `m2_sighted/ckpt/iter_00..04.pt` | `score_diff_wide` = tanh((p0−p1)/40), **absolute** | target clean, value head weak | 5-iter sighted self-play (warm from `warmstart_sighted.pt`), leaf=`sighted_nn_head`. Value head **near-inert** — **M2 KILL** (CL-039/042, 2026-07-03): solver-τ 0.02 vs v2.9 leaf 0.615 (~27× worse). Trunk/policy fine; value poor. |
| `c_cheap_value/value_head*.pt` (v1) | `score_diff_wide`, **absolute** | no (value-ONLY, blind trunk) | Value-only head, trunk warmed from the **blind** `flywheel_residual_attempt2/iter8`. **DEAD** — CL-049: W0/L100, avg_diff −58 as a leaf replacement. |
| `c_cheap_value_v2/value_A.pt`, `value_B_zerobag.pt` | **RESIDUAL** `clip(z−tanh(leaf/15),−1,1)` | **NO — residual baggage** | Value-only residual-over-leaf head (needs the leaf at inference). **DEAD** — CL-050: online +9.2 elo = null. **⚠️ Metadata trap:** both stamp `value_target="score_diff_wide"` but the real learned target is the residual (hardcoded stamp at `train_value_only_sighted.py:297`) — don't trust the stamp for these two. |

**Warmstart-producing capability (Path-B fallback):** `train_warmstart.py --sighted` (`:157–162,247,397–419`)
builds the 81ch net and saves `n_input_channels=81`/`sighted=True`; `generate_warmstart_smoke.py --sighted`
(`:100–104`) emits the dataset. The sighted warmstart dataset is already on disk:
`data/warmstart/heuristic_tau05_sighted/` (10,000 shards, **verified** `(N,81,25,25)` / `(N,42)`, absolute
tanh-value). So a fresh sighted warmstart is a ~1–2 h GPU run if ever wanted — but it is **not needed**,
because `warmstart_sighted.pt` already IS that net.

### Fork verdict → **Path A (same-day)**
`/mnt/c/carc-shared/m2_sighted/warmstart_sighted.pt` is the clean sighted analog of `warmstart_canonical.pt`
(same warmstart pipeline, same 96×6 arch, absolute-value head, no baggage, carries the `sighted`/
`n_input_channels` keys `train_iter` reads). It drops straight in as iter-0 warm-from. **No warmstart
training run.** The M2 self-play `iter_0N.pt` are NOT preferred (their value head is the killed near-inert
one); use the fresh warmstart. The C-cheap v1/v2 nets are value-only / residual and unsuitable.

Context on the kill history (important for expectations, not a blocker): the sighted rep was explicitly
built for the CL-033 "value resurrection" thesis (`sighted_planes.py:1–8`) and every attempt to make its
*value* head beat the v2.9 leaf failed — M2 (sighted AZ value) and C-cheap v1/v2 (deck-aware value) are all
DEAD (8th value-inertness null). This flywheel **severs the value loop** (frozen leaf value; net = policy
priors only), so those kills don't apply to the distillation, but they are strong prior evidence that
sighted's payoff here is **policy fidelity + a bag-aware substrate**, not a strong learned value.

- **Training the distill net from scratch (no warm)** — not recommended. Stage-1 is only 4 distill iters;
  a cold net's probe-fidelity curve (the only ruler; no game eval) would be dominated by warm-up transients,
  and the ≤4-iter budget can't amortize it. Only if `warmstart_sighted.pt` proves unusable.

---

## 3. Change-list + effort estimate (Path A)

All changes are additive/opt-in; nothing about the non-sighted path is deleted.

| # | File | Change | Notes |
|---|------|--------|-------|
| 1 | `scripts/distill_flywheel/gen_fair_distill.py:155` | `encoder = Game(window_size=window_size)` → `encoder = Game(sighted=True, window_size=window_size)` | The referee `game` (`:149`) stays non-sighted (deck driver). Mirror the original `gen_fair_selfplay.py:161–162` pattern (referee vs sighted encoder). Also fix stale comments `:139,150–154,329` (they currently say "NON-sighted 78ch") and the already-stale array-shape comments `:228–229` (they wrongly say `(N,81)`/`(N,42)`). |
| 2 | iter-0 warm-from | Use the existing `/mnt/c/carc-shared/m2_sighted/warmstart_sighted.pt` (Path A) | **No train run.** Arch-confirmed 81ch/42, clean absolute value. (Path-B fallback: `train_warmstart.py --sighted` on `heuristic_tau05_sighted`, ~1–2 h.) |
| 3 | `scripts/distill_flywheel/run_distill_stage1.sh:52` | `WARM0=...checkpoints/warmstart_canonical.pt` → `WARM0=/mnt/c/carc-shared/m2_sighted/warmstart_sighted.pt` | iter-0 warm-from; warm-chaining (`_warm_for`) then propagates sighted automatically iter→iter. Sanity-check it loads: `torch.load(...)['n_input_channels']==81`. |
| 4 | probe set `probe_data/iter_00/seed_*.npz` | **Regenerate** with the sighted emitter (same 24 champ games, seeds 699000000+) | The current probe is 78ch (verified on disk); a sighted net can't forward it. Same emitter (#1) → gen'ing the probe with it yields sighted probe automatically. ~15 min, local W16. |
| 5 | `train_iter.py` | **NONE** | Already reads `sighted/n_input_channels/n_scalar_features` from warm-from (`:473–482`) and propagates (`:767–770`). |
| 6 | `probe_metrics.py` | **NONE** | Reads net dims from ckpt (`:49–50`), loads probe shards (`:58–73`); rep-agnostic *as long as* probe and net agree (they will, via #1+#4). |
| 7 | Stage-2 (iters 4–11) not yet built | Build `make_fair_net_prior_evaluator` **sighted-aware** from the start | Per `DESIGN_FAIR_ADDENDUM.md:34` this factory is new. Its net forwards must encode boards with `Game(sighted=True)`. The champion side-stream reuses `gen_fair_distill.py` → already sighted via #1. Not a "change", but a consistency requirement to lock in now so stage-2 isn't built blind. |

**Relaunch effort (Path A):** ~15 min probe regen (#4) + emitter/config edits (#1,#3, minutes) + stage-1
smoke (the addendum's 1-game fair smoke) → relaunch iters 0–3. **~1 h wall**, no warmstart GPU run (the clean
sighted warm-from already exists). Discards the 2–3 non-sighted iters already computed. (Path-B fallback adds
~1–2 h if a fresh warmstart is ever preferred.)

---

## 4. Pipeline-consistency checklist (must all agree on 81ch/42, or it breaks)

Every stage that touches the representation. A mismatch **raises** (conv/`cat` shape error) — no silent
mis-train — but a *forgotten* stage still aborts the run, so all must move together:

1. **Emitter** `gen_fair_distill.py` — `encoder = Game(sighted=True)` (#1). Emits `boards (N,81,W,W)`,
   `scalars (N,42)`. Referee `game` stays non-sighted (fine — it's the deck driver, not encoded).
2. **iter-0 warm-from** `m2_sighted/warmstart_sighted.pt` (#2/#3) — carries `n_input_channels=81`
   (+ `sighted=True`). If a 78ch warm is left in place with 81ch data → `RuntimeError` at the stem conv
   (81-in-channel data vs 78-in-channel weight). **Loud, not silent.**
3. **train_iter.py** — no change; builds the net from the warm-from's dims. Warm-chaining propagates sighted
   iter→iter automatically because each `iter_NN.pt` is saved with `sighted/n_input_channels` (`:767–770`).
4. **Frozen probe set** `probe_data/iter_00/` — regenerate sighted (#4). A 78ch probe into an 81ch net →
   `RuntimeError` in `probe_metrics._load_probe`→forward. **Loud.**
5. **probe_metrics.py** — no change; rep-agnostic given #4.
6. **Stage-2 fair-net evaluator** (`make_fair_net_prior_evaluator`, not yet built) — must encode net-prior
   inputs with `Game(sighted=True)` (#7). Also verify the **carc-orch** context is created around the 81ch
   net so batched forwards accept 81ch tensors (the orch inherits the net's input shape; flag as a launch
   check, not a code change).
7. **Window:** flywheel uses `--window 12`; the warmstart dataset is window-25. This is **already the status
   quo** (warmstart_canonical trained @25 warms a window-12 flywheel today) — the ResNet + global-pool head
   is spatially agnostic in parameter count, so window size does not change arch. **Not a blocker.**

Silent-failure audit: I found **no** path where an 81/78 mismatch would train silently — the stem conv and
the scalar `cat` both hard-error on shape. The only real failure mode is "forgot to regen the probe / swap
the warm-from" → crash on launch, caught immediately by the addendum's stage-1 smoke.

---

## 5. Recommendation (restated, decision-grade)

1. **Is sighted sound / fair-safe?** YES, with code proof (§1). The bag histogram is an order-agnostic
   public multiset; the farm planes are board-derived. No deck-order / future-draw / next-N feature exists
   in the module. It does not reintroduce clairvoyant strategy-fusion — it exposes exactly the public bag
   the fair champion already reasons over. This is the make-or-break gate and it passes.
2. **Is it worth doing?** For a *faithful fair* distillation, yes — the net gets the same public bag
   knowledge the teacher marginalizes over, which is the legitimate input for a bag-aware blind policy
   (this was literally the CL-033 hypothesis: the 78ch value head is inert partly because it's blind to the
   bag). Sighted also keeps the net's inputs coherent with a deployable bag-aware iter-12.
3. **Cleanest path:** **Path A (same-day).** Point WARM0 at the existing
   `/mnt/c/carc-shared/m2_sighted/warmstart_sighted.pt` (clean sighted 81ch/42, no baggage), regen the probe
   sighted (~15 min), flip the emitter encoder (`gen_fair_distill.py:155` → `Game(sighted=True, ...)`), smoke,
   relaunch iters 0–3. **~1 h wall, no warmstart training run.** train_iter/probe_metrics need no code change.
   But temper the value-head expectation given the 8× sighted-value-inertness kill history (M2 / C-cheap) —
   the win here is POLICY fidelity + a bag-aware substrate, and the flywheel's severed value loop makes those
   kills inapplicable to *this* run.
4. **Caveat / cost-discipline:** switching discards the 2–3 non-sighted iters already computed. If
   non-sighted was chosen as the *cheap baseline*, the highest-value play is to let it finish (nearly done)
   and run sighted as a clean A/B — the frozen probe (policy CE / top-1 / value_r) is directly comparable
   across the two reps, which directly tests the CL-033 "is the net inert because it's bag-blind?" question
   for the price of one extra stage-1.

---

### File/line index (evidence)
- `src/carcassonne_ai/sighted_planes.py` — sighted rep: farm planes `:138–173`, bag histogram `:176–194`,
  frozen 72-tile/32-type census `:45–87`, "structural, no label leak" docstring `:24–28`.
- `src/carcassonne_ai/game_wrapper.py` — `sighted` flag `:273/:309`, `get_input_channels` `:360–366`,
  `get_scalar_feature_size` `:374–379`, sighted apply `:589–602`.
- `src/carcassonne_ai/board_repr.py:107` (N_CHANNELS=78); `features.py:38–39` (10 scalars + 2 farm).
- `scripts/distill_flywheel/gen_fair_distill.py` — referee `:149`, non-sighted encoder `:155`, record vs
  play `:175/:188`.
- `scripts/canonical_az/gen_fair_selfplay.py:161–162` — original referee/sighted-encoder pattern to mirror.
- `scripts/train_iter.py:473–482` (reads sighted/dims from warm-from), `:767–770` (propagates).
- `scripts/train_warmstart.py:157–162,247,397–419` (--sighted, saves the keys), default 96×6 `:140–141`.
- `scripts/generate_warmstart_smoke.py:100–104` (--sighted dataset emitter).
- `data/warmstart/heuristic_tau05_sighted/` (10k shards, verified 81ch/42, absolute value).
- **`/mnt/c/carc-shared/m2_sighted/warmstart_sighted.pt`** (+ `.best.pt`) — the clean sighted warm-from
  (81ch/42, sighted=True, 96×6, absolute value, no baggage). M2 self-play `m2_sighted/ckpt/iter_00..04.pt`
  (absolute value but killed near-inert value head).
- C-cheap value nets: `/mnt/c/carc-shared/c_cheap_value/value_head*.pt` (v1 absolute, CL-049 dead),
  `/mnt/c/carc-shared/c_cheap_value_v2/value_{A,B_zerobag}.pt` (v2 residual baggage, CL-050 null,
  misleading `score_diff_wide` stamp @ `scripts/canonical_az/train_value_only_sighted.py:297`).
- Kill history: `DECISIONS.md` 2026-07-03 (M2 KILL, CL-039/042) & 2026-07-10 (C-cheap CL-049/050);
  `docs/AZ_VALUE_ROUTE_AUTOPSY_2026-07-01.md`; `measurement/classical_search/C_CHEAP_SPEC_2026-07-09.md`.
- `checkpoints/warmstart_canonical.pt` (78ch, from `data/warmstart/heuristic_tau05`, no sighted keys).
- `measurement/distill_flywheel_20260715/DESIGN_FAIR_ADDENDUM.md` (fair pivot spec), `DESIGN.md:25`
  (non-sighted public-info verification), `:85` (probe_metrics), `run_distill_stage1.sh:52` (WARM0).
