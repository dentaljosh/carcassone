# P1 gap G3 — label-variance decomposition: what an outcome objective can learn from vs what search consumes

> **STATUS: ✅ DONE 2026-08-02.** Closes `docs/papers/p1_prediction_vs_discrimination/CLAIMS_LEDGER.md`
> gap **G3** (`TODO-MEASURE` → `DONE`) and promotes ledger row **D1** from interpretation
> to a measured decomposition.
> **Offline arithmetic only** — no games, no search, no net forward, no GPU. Every
> number below is reproducible from files already on disk by re-running the four
> scripts in this directory.
> **Machine-readable:** [`G3_VARIANCE_DECOMP.json`](G3_VARIANCE_DECOMP.json) ·
> **figure table:** [`G3_FIGURE_DATA.csv`](G3_FIGURE_DATA.csv)

---

## 1. The question

Ledger row D1 states the mechanism as an interpretation:

> *"The outcome label at a decision point is nearly common across siblings; MSE reduction
> is available from the shared component without resolving the between-sibling residual."*

G3 asks for the arithmetic behind "nearly common": decompose the variance of the value
head's label into (a) the components an outcome-regression objective can reduce its loss
on, and (b) the between-sibling component that argmax and Kendall tau — i.e. move
selection — actually consume.

Two decompositions are needed because the training corpus and the discrimination ruler
are different objects:

1. **The corpus** (`distill_strong_20260723`, 2,400 games / 345,333 rows) has the *actual
   training labels* but **no sibling structure at all** — it stores one row per decision,
   the position resulting from the move that was played.
2. **The ruler bank** (1,119 exact-solver K=2 roots / 50,637 children) has *counterfactual
   sibling values* — the exact endgame solver's value for **every** legal child of each
   root. This is the level search consumes, and it is where the paper's primary
   statistics (regret / top-1 / tau) are measured.

So the decomposition is run on both, and the second is the answer to "what if the labels
had been perfect and counterfactual?".

## 2. Inputs (all pre-existing; nothing was regenerated)

| role | path | fingerprint / size |
|---|---|---|
| training corpus | `/mnt/c/carc-shared/distill_strong_20260723/iter_00..03/*.npz` | 2,400 files, 345,333 rows; file-list sha256 `24c2e468824bc9e5…` |
| corpus provenance | `…/iter_00/manifest.json` | `gen_fair_distill`, net-free champion, k8×1376 = 11,008 sims/move, `value_target_desc` = "mover-POV tanh((p0−p1)/15) backfilled from the FINAL score" |
| sibling bank | `measurement/gatec_c0_20260723/cache/c0_cache.npz` | sha256 `6bbe7a4a4f066391…`; 1,119 roots × 50,637 children; exact solver `y` (mover-POV, raw points), `leaf_score`, `group` |
| bank provenance | `measurement/gatec_c0_20260723/cache/manifest.json` | `n_roots: 1119`, `mode: marginalized (K<=2)`, `leaf_self_check` = regret **0.9508** / top1 **0.6095** / tau **0.6153** |
| phase panel (supplementary) | `measurement/high_gap_distillation/scaled/qprobe_A/probe.jsonl` | sha256 `eb9a65c589535772…`; 10,067 roots × 314,911 children of h6400 `action_q` |
| imported numbers | `measurement/value_unlock_20260730/READOUT.md`, `VERDICT.json` | r = 0.6795 / 0.6564; tau = 0.0190 / 0.0177 / 0.6153 |

**Provenance self-checks (both passed, computed fresh in `g3_sibling_decomp.py`):**

- the leaf arm on this bank recomputes to regret **0.9508489722966935**, top-1
  **0.6094727435210009**, tau **0.6152820150615235** — identical to the READOUT §4.1
  `curve125` row and to `solver_score_derisk_it00_03.json`;
- the supplementary ridge recomputes to tau **0.34654**, top-1 **0.46381**, regret
  **0.78999** — identical to CL-065's `gate_full_ridge` (0.3466 / 0.4638 / 0.7900).

The bank's leaf config is curve100; READOUT §4.3(b) records that curve125 and curve100
pick **the same child on 1,119/1,119 roots** here, so the reference arm is the champion's
leaf for every purpose in this document.

## 3. Method

One-way variance decomposition by grouping level *G*:

    SS_total = SS_between(G) + SS_within(G),   SS_between = Σ_g n_g (ȳ_g − ȳ)²

reported as fractions of `SS_total`. Levels used:

- **corpus:** grand → game → (game × side-to-move) → position/row. The label is mover-POV,
  so a game contributes exactly two values ±c_g; the `game × side` cell is the finest
  level at which the label can still differ.
- **sibling bank:** grand → root (= the sibling set) → child. `between-root` is the
  position-level component; `within-root` is the between-sibling residual.

The solver label is also expressed as `tanh(y/15)` — the *same units as the training
target* — so the two decompositions are commensurable.

## 4. Results

### 4.1 The training label has **zero** variance below the (game × side) level

| level | SS | fraction of total |
|---|---|---|
| total (345,333 rows, mover-POV) | 174,748.876 | 1.000000 |
| between (game × side-to-move) | 174,748.876 | **0.9999999997** |
| within (game × side) = **between positions** | −1.90e−12 | **−1.09e−17 ≈ 0** |
| between siblings | — | **0 by construction** |

- The label's absolute value is **exactly** constant within a game: the maximum
  within-game range of `|label|` across all 2,400 games is **0.0**, and **0 of 2,400**
  games contain more than one `|label|` value. Its sign is decided solely by whose turn
  it is. So conditioning on (game, side) leaves **no residual variance at all** — the
  within-cell SS is −1.9e−12 against a total of 1.75e5, i.e. float round-off.
- `group_id == −1` on all 345,333 rows: the corpus never stores a sibling set. There is
  no between-sibling level in the training data to learn from.
- Sanity: the label sd recomputes to **0.7113578927846519** vs the READOUT §1.3 figure
  **0.711358**. Mean label 8.58e−5; 2,400 games; 143.9 rows/game; 4,716 non-degenerate
  (game × side) cells (42 games are exact draws, c_g = 0).

**Effective independent labels: 2,400 games (4,716 cells) behind 345,333 rows** — the
arithmetic form of CL-066's "value ESS is games, not positions" (ledger row B8).

### 4.2 Even with perfect counterfactual labels, the sibling level is ~0.3% of the variance

1,119 roots, 50,637 children, 45.25 children/root (median 44, min 8, max 116):

| quantity | units | sd (total) | frac between-root | frac **within-root** | sd within-root |
|---|---|---|---|---|---|
| exact solver child value | raw points | 22.1268 | 0.9971906 | **0.0028094** | 1.1728 |
| exact solver child value | tanh(·/15) — *training-target units* | 0.7345 | 0.9965473 | **0.0034527** | 0.04316 |
| **hand-crafted leaf value** (reference arm) | tanh(·/15) | 0.7371 | 0.9983365 | **0.0016635** | 0.03006 |
| pooled-MSE ridge prediction (supplementary) | raw points | 21.9968 | 0.9984977 | **0.0015023** | 0.85258 |

- **11.53%** of roots have *zero* within-root variance in the solver labels (every legal
  move is exactly equivalent); for the leaf it is 13.49%.
- Per-root within-root sd (unweighted over roots): solver **0.02517** mean / **0.01233**
  median in tanh units.
- Scale: the between-sibling residual sd in the head's own target units is **0.04316**,
  i.e. **6.07%** of the training label's sd (0.71136).
- The *entire* between-sibling residual variance is **0.0018625** (tanh units), which is
  **0.688%** of `value_unlock_v1`'s best held-out value MSE (0.2708). ⚠️ Cross-instrument
  and indicative only — numerator from 1,119 K=2 endgame roots, denominator from sampled
  game outcomes over all plies of 120 held-out games; same units, different distributions.

**The position-level ceiling.** A predictor that knows each root's mean exactly and
nothing else explains **R² = 0.99719** of the exact-label variance and has, by
construction, **Kendall tau = 0** between siblings. That is the whole of D1 in one row.

### 4.3 The reference arm splits its skill the other way

Leaf vs exact solver, same 50,637 children:

| level | statistic | value |
|---|---|---|
| pooled | Pearson r | 0.93170 |
| between-root | Pearson r | 0.93227 (r² 0.86912) |
| within-root | Pearson r, points scale | 0.44048 (r² 0.19402) |
| within-root | Pearson r, matched tanh units | 0.52130 |
| within-root | Pearson r, residuals z-scored per root (937 roots / 41,914 children) | 0.61719 |
| within-root | **Kendall tau-b (primary, per-root mean)** | **0.61528** |

The leaf is *not* a better position-level predictor than a learned model — the
supplementary pooled-MSE ridge on the leaf's own 84 component features reaches
**between-root R² = 0.98956** against the leaf's 0.86912 — yet the ridge's within-root
tau is **0.34654** against the leaf's **0.61528**. Position-level accuracy and
sibling-level ordering are separately purchasable, and the leaf bought the second.

⚠️ **One honest disagreement between statistics, recorded so nobody trips on it:** the
ridge's within-root *linear* correlation (z-scored, 0.68297) exceeds the leaf's (0.61719)
while its *rank* tau is half. Tau/top-1/regret are the paper's pre-registered primary
statistics and are what search consumes (argmax is a rank operation); the within-root
Pearson is a secondary diagnostic that weights roots and children differently and can
disagree. Do not quote the Pearson as a discrimination verdict.

### 4.4 Supplementary — the split across game phase (h6400 search Q, not ground truth)

The exact bank is K=2 only (ledger row E5). The only whole-game sibling-structured values
on disk are the h6400 deep-search `action_q` values. ⚠️ These are a **search estimate**
that correlates **0.995** with the v2.9 leaf (autopsy F4) — the exact reason the paper's
ruler is the solver instead. Use for **shape only, never as a verdict**.

| k_remaining | n_roots | n_children | sd within-root | frac within-root |
|---|---|---|---|---|
| 2 | 1119 | 41452 | 0.036408 | 0.2463% |
| 4 | 1119 | 40565 | 0.039418 | 0.2830% |
| 6 | 1120 | 40815 | 0.042403 | 0.3366% |
| 10 | 1119 | 39567 | 0.043126 | 0.3596% |
| 14 | 1119 | 38309 | 0.048251 | 0.4616% |
| 22 | 1120 | 35839 | 0.053357 | 0.6314% |
| 32 | 1119 | 32534 | 0.062712 | 1.0162% |
| 44 | 1119 | 26120 | 0.104481 | 5.1797% |
| 56 | 1113 | 19710 | 0.100713 | 8.9232% |
| **all** | **10067** | **314911** | **0.058268** | **0.7491%** |

Monotone in phase: the between-sibling share is largest in the opening (8.92% at 56 tiles
remaining) and smallest in the endgame (0.25%), but **never exceeds ~9%** anywhere in the
game. The endgame-only scope of the exact bank is therefore the *most* favourable region
for the shared-component story and the *least* favourable for the learned head; the
midgame would move the fraction by well under an order of magnitude, not reverse it.

## 5. Figure spec — F-G3 "the level the label lives at"

Data table: [`G3_FIGURE_DATA.csv`](G3_FIGURE_DATA.csv) (29 rows; columns
`panel, series, x, y, label, unit, source`). No plotting library required — the numbers
are the deliverable; the caller draws it in whatever the venue wants.

- **Panel A — variance share by level** (horizontal stacked bars, 4 rows; log-scaled or
  broken axis strongly advised since every "sibling" segment is ≤0.9%).
  Rows: *training outcome label* (game × side 100.0000% / positions 0.0000% / siblings
  0 — absent by construction) · *exact solver child value, tanh units* (99.6547% /
  0.3453%) · *hand-crafted leaf value* (99.8337% / 0.1663%) · *h6400 search Q, all
  phases* (99.2509% / 0.7491%, marked supplementary).
  Annotation: "R² = 0.99719 available with tau = 0."
- **Panel B — between-sibling share vs game phase** (line, x = `k_remaining` 2…56,
  y = fraction within-root, log y). Nine h6400 points plus the exact-solver K=2 point
  (0.003453) as a filled marker. Caption must carry the 0.995 leaf-correlation caveat.
- **Panel C — position-level skill vs sibling-level skill** (paired dot plot / slope
  chart, one row per ranker, two x-axes). Rows: `value_unlock_v1` (r 0.6795 → tau 0.0190)
  · `iter_03` (0.6564 → 0.0177) · hand-crafted leaf (≈0.61 → 0.6153) · root-mean oracle
  (R² 0.99719 → tau 0.0) · pooled-MSE ridge (R² 0.98802 → tau 0.34654, supplementary).
  This is the paper's headline dissociation and the ledger's F8 warning in one picture.

Constraints inherited from the ledger: **[VERBATIM]** (re-read from
`G3_VARIANCE_DECOMP.json` at typesetting), **[RULER]** on Panel C (name the ruler: exact
endgame solver, 1,119 K=2 marginalized roots), and the walled-variant posture — these are
variance shares of *this engine's* corpora, not of canonical Carcassonne.

## 6. Interpretation, in the paper's terms

> The value head's training signal and the quantity search consumes are not merely
> different in emphasis; they are separated by three orders of magnitude in variance. The
> label the head regresses on — `tanh((p0−p1)/15)`, backfilled from the final score — is
> *exactly* constant within a game: across all 2,400 games and 345,333 positions of the
> strongest corpus the program can produce, the label's magnitude never varies inside a
> game (maximum within-game range 0.0), and once the game and the side to move are known,
> the residual variance is zero to float precision. Every position in a 144-ply game
> carries the same number. Search, by contrast, consumes only the *contrast between
> siblings at one decision point*, and the corpus does not contain sibling sets at all
> (`group_id == −1` on every row): the between-sibling component of the training signal is
> not small, it is absent. Supplying it counterfactually does not rescue the picture. On
> the 1,119-root exact-solver bank — the same bank on which the head loses to the leaf
> 2.10× in regret and 32× in tau — the perfect, exhaustive, counterfactual label puts
> **99.72%** of its variance *between* roots and **0.28%** *within* them (0.35% in the
> head's own tanh units; 11.5% of roots have no within-root variance at all, every legal
> move being exactly equivalent). The consequence is exact rather than rhetorical: a
> predictor that knows each root's mean and nothing else attains **R² = 0.99719** on the
> exact labels while carrying, by construction, **Kendall tau = 0** over siblings. That is
> the whole distance between the head's improved outcome correlation (r 0.6564 → 0.6795,
> above the ≈0.61 heuristic reference) and its inert discrimination (tau 0.0177 → 0.0190
> against the leaf's 0.6153, paired sign-z +0.97 vs its own parent). An MSE objective is
> not being lazy when it spends its capacity on the shared component — 99.7% of the loss
> it is scored on lives there, and the entire residual search needs is worth roughly 0.7%
> of the head's held-out value MSE. The hand-crafted leaf is a *worse* position-level
> predictor than a pooled-MSE ridge fitted to its own 84 component features (between-root
> R² 0.869 vs 0.990) and a **1.8×** better sibling ranker (tau 0.615 vs 0.347), because its
> terms were selected and weighted by paired game outcomes *of the discrimination channel
> itself* (D2). The mechanism is therefore not "the network is too small" (B5), "the
> representation is wrong" (B6), or "the teacher was weak" (A7): it is that outcome
> regression is scored almost entirely on a quantity that move selection discards, and the
> quantity move selection keeps is a sub-percent residual the objective is nearly
> indifferent to. Prediction and discrimination dissociate here because the label makes
> them nearly orthogonal by construction.

## 7. Scope and caveats

1. **This is a decomposition of labels, not a proof about learnability.** It shows the
   objective's *scoring* is dominated by the shared component; it does not prove no
   architecture or objective could extract the residual. The complementary evidence for
   that is the ledger's closure ladder (B5/B6) and the LTR counterpoint (C4: a *ranking*
   objective does beat the leaf offline — consistent with this decomposition, since a
   ranking loss deletes the between-root component from the objective).
2. **The exact bank is K=2 endgames** (ledger E5). §4.4's phase curve is the only
   whole-game evidence and rests on the h6400 oracle, which is 0.995-correlated with the
   leaf; it bounds the shape, not the verdict.
3. **§4.2's last bullet crosses instruments** (solver bank variance vs corpus held-out
   MSE). It is labelled indicative in the JSON and should be quoted as "roughly", or
   dropped, in the manuscript.
4. **The corpus decomposition covers labels, not features.** Positions within a game
   differ enormously; it is the *target* that does not. That is precisely the claim.
5. **[WALL]** These are variance shares measured on the engine's rules variant (ledger
   E1), like every other number in this paper.
6. No new claim registry row was created; this measurement supports existing rows
   **D1** (promoted from interpretation) and **B8**, and is consistent with **A1–A6**.

## 8. Files

| file | what |
|---|---|
| [`g3_corpus_scan.py`](g3_corpus_scan.py) | corpus label decomposition (2,400 npz, threads=8, `nice -19`) → [`g3_corpus_decomp.json`](g3_corpus_decomp.json) — 3.0 s |
| [`g3_sibling_decomp.py`](g3_sibling_decomp.py) | sibling bank decomposition + leaf reference + supplementary ridge → [`g3_sibling_decomp.json`](g3_sibling_decomp.json) — 3.7 s |
| [`g3_phase_curve.py`](g3_phase_curve.py) | supplementary phase panel → [`g3_phase_curve.json`](g3_phase_curve.json) — 0.3 s |
| [`g3_assemble.py`](g3_assemble.py) | combines the three + derived ratios → [`G3_VARIANCE_DECOMP.json`](G3_VARIANCE_DECOMP.json), [`G3_FIGURE_DATA.csv`](G3_FIGURE_DATA.csv) |
