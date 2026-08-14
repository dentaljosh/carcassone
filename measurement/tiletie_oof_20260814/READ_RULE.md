# TILE-TIE OUT-OF-FAMILY RE-PRICING — READ-RULE

> **STATUS AT WRITING: COMMITTED BEFORE ANY OUT-OF-FAMILY NUMBER EXISTS
> ANYWHERE — before the instrument, before the cost pilot, before the run.**
> `READOUT.md`, `READOUT.json`, `PILOT.json` do not exist at the time of this
> commit. Git history proves the ordering. Definitions (corpus, dev slice,
> arms, judges, CRN convention, S1a / S2, the zero add-back scales, the ×1.40
> full-set extrapolation, the ÷3.2 elo chain) are frozen here by reference to
> [DESIGN.md](DESIGN.md) §3–§5 and to
> [../tiletie_pricing_20260812/DESIGN.md](../tiletie_pricing_20260812/DESIGN.md)
> §4.

**This read-rule is fully mechanical.** Every branch is a boolean function of
numbers the analyser emits. No owner call adjudicates any outcome. It is spent
on this judge and this slice; any successor design needs a fresh one.

---

## 1. Scope

- **Main read: the pricing corpus's DEV slice minus the §6 cost pilot** —
  502 positions / ≈ 271 roots (522 dev positions, seed 2026081402 split, minus
  20 seeded pilot positions, seed 20260814). A partially-completed run is read
  at its realized `n` because the position order is a committed seeded
  permutation, so every prefix is a uniform random subsample (DESIGN §6).
- ⛔ **The holdout — `../tiletie_mining_20260814/HOLDOUT_ROOTS.json`, 120 roots
  / 211 positions — is NEVER read, on ANY branch, by ANY instrument in this
  directory.** It stays unburned. No branch below opens it and none ever may.
- **0 games on every branch.** No `experiments/results.csv` row, no band, no
  `governance/BAND_REGISTRY.csv` entry, no claim id, `governance/PRODUCTION.yaml`
  untouched — regardless of outcome.

## 2. The committed quantities

All computed by `scripts/tiletie/analyze_tiletie.py` (unmodified) on the same
502 positions for **both** judges, then joined by `scripts/tiletie/analyze_oof.py`.
`IF` = in-family `clair-puct` (the existing records); `OOF` = out-of-family
`tier1-greedy` (the new records).

| symbol | definition |
|---|---|
| `H_OOF` | S2 `headroom_J4`, **`all` scaling** (zeros added at population share), under OOF, over the main-read positions [pts/tied tile ply] |
| `se_OOF` | cluster-robust se on `root_id`; **`z_OOF = H_OOF / se_OOF`** |
| `z_swap_OOF` | the same S2 statistic under the **swapped** parity split, under OOF (the pricing readout's `parity_swap` diagnostic) |
| `H_IF`, `z_IF` | the identical statistic under IF, on the **identical** positions |
| **`R`** | **`H_OOF / H_IF`** — the retention ratio. 95% CI `[R_lo, R_hi]` from a **root** bootstrap, 20,000 reps, seed **20260814**, recomputing *both* judges inside each rep (so the CRN cross-judge correlation is priced automatically) |
| `R_norm` | `(H_OOF / sqrt(max(0, S1a_OOF))) / (H_IF / sqrt(max(0, S1a_IF)))`, `S1a` = the `all`-scaled σ²_arm. **If `S1a_OOF ≤ 0`, `R_norm := 0.0`** (no between-arm spread at all ⇒ zero retention). |
| `G-CAL` | PASS iff the DESIGN §4.5 cross-judge cross-parity control returns sign-aligned cluster-robust **`z ≥ +2.0`** |

**The bar is `0.50`** — half the in-family headroom retained. It is not a new
constant: half of the pooled `+34.49` elo headline is `≈ +17.2 elo`, i.e. the
project's own **±17-elo resolution bar** (`ELO_CLOSE_BAR = 17.0`,
`analyze_tiletie.py:66`), which is the threshold the entire tile-tie axis has
been adjudicated against since 2026-08-13. `R < 0.50` therefore means *"what
survives out of family is below the bar the axis is decided at."*

## 3. Preconditions — checked first, and they void the run

**`U-UNREADABLE` fires, and no other branch may fire, if ANY of:**

| id | condition |
|---|---|
| `G-CRN` | any scored record has `crn_verified != true`, `checksum_ok != true`, or `world_seeds`/`playout_seeds` not **bit-identical** to the in-family record for the same `rid` |
| `G-ARM` | any record's `pick_a`/`pick_b` disagrees with `ARMS.json` for its leg, in either judge |
| `G-VA` | `values_a` not bit-identical across all legs of a position, within either judge |
| `G-HOLDOUT` | any `root_id` from `HOLDOUT_ROOTS.json` appears in the plan, the records, or the analysis |
| `G-PILOT` | any §6 pilot rid enters the main read |
| `G-N` | fewer than **250** positions complete |
| `G-DENOM` | `H_IF ≤ 0`, or `z_IF < +2.0`, or `S1a_IF ≤ 0` — **the in-family signal is not itself convicted on this slice, so there is nothing to re-price and `R` has no meaningful denominator** |

`U-UNREADABLE` = report cost, integrity and whatever gate failed. **Nothing
closes, nothing is licensed, nothing is re-labelled.** The holdout stays
unburned.

## 4. Branches

Let `C ≡ (z_OOF ≥ +2.0)`. Let `K ≡ (R_hi < 0.50 ∧ R_norm < 0.50 ∧ G-CAL PASS)`.

| # | condition | read |
|---|---|---|
| **`C-CONFIRM`** | `C` **∧** `R ≥ 0.50` **∧** `R_norm ≥ 0.50` **∧** `z_swap_OOF > 0` | **THE SIGNAL IS REAL OUT OF FAMILY.** A judge sharing neither the leaf nor the search sees at least half the headroom, and convicts it at 2σ on its own scale. The +0.252 is **not** substantially a judge artifact. **Licenses (does NOT fund) exactly one thing: a fresh pre-registration on the k-width / determinization-at-ties axis** — the one axis `docs/LEVER_INDEX.md`'s re-open bar names that has never been tried — **and that prereg must name its MECHANISM before it may spend compute**, because three capture routes have already read flat and "try harder on the same axis" is not a mechanism. ⛔ It does **not** license a leaf term (CL-065 kills the learned route representation-independently; two hand-crafted menus have failed; the 38% reach bound stands). ⛔ It does **not** license a game, a band, or a deploy. The **±17-elo Stage-B question stays OPEN**, and its only honest route remains supply (`n ≈ 1023`, pricing readout §6) — not licensed here. |
| **`X-COLLAPSE`** | `¬C` **∧** `K` | **THE +0.252 IS SUBSTANTIALLY A JUDGE ARTIFACT ⇒ THE TILE-TIE AXIS CLOSES ENTIRELY.** Out of family, half-retention is **excluded** (`R_hi < 0.50` on both the pts and the noise-normalised reading) and the out-of-family judge does not convict any positive headroom — while `G-CAL` shows that same judge **does** resolve the contrasts the in-family judge calls its largest. Closure includes **the ±17-elo Stage-B question**: extending supply to `n ≈ 1023` would only sharpen a number the ruler partly invented, so it is closed too, not merely unfunded. No successor measurement on this axis. ⚠️ **The mandatory scope sentence, quoted with the closure and never separated from it:** *"This closes the headroom visible to EITHER an in-family clairvoyant PUCT search over the leaf under test OR an out-of-family greedy continuation on the same clairvoyant decks — a materially stronger statement than the pricing run alone supported, but still not 'headroom in truth'. A greedy continuation is a different estimand, and DESIGN §8 threat 1 bounds it only partially: `G-CAL` shows the judge resolves the primary's largest contrasts, not that it resolves deck-dependent tactical ones specifically."* |
| **`P-BLIND`** | `¬C` **∧** `¬K` **∧** `R_lo ≤ 0.0` | **UNRESOLVED — THE OUT-OF-FAMILY LEG DID NOT DECIDE.** The data excludes neither substantial retention nor zero (or `G-CAL` failed, i.e. the judge cannot resolve even the primary's largest contrasts and its null is uninformative by the project's standing false-negative rule). **Nothing closes and nothing is licensed.** The +0.252 keeps its pricing §5 caveat *verbatim and undischarged*. The honest successor is named, not started: **a leaf-override judge channel** (DESIGN §2.2 — the `c5_leaf_override.py` / `solver_score.py --leaf-variant` dialect wired into `ORACLE_POLICIES`), which needs its own identity gate and its own read-rule. Report the realized 2σ resolution in pts and elo and the `n` that would have decided. |
| **`B-PARTIAL`** | otherwise | **ATTENUATED BUT PRESENT, OR CONVICTED BUT SMALL.** The out-of-family judge sees a positive headroom that is real but below half, or convicts without both ratio readings clearing the bar, or the two ratio readings **straddle** it. **Nothing closes and nothing is licensed** — in particular this does **not** close the axis and does **not** fund a successor. Report `R`, `R_norm`, the CI, which conjunct failed, and the `n` that would resolve `R` to ±0.25. |

### 4.1 Exclusivity and exhaustiveness — verified in the pre-registration text

Per the pricing DESIGN's own §4.4-A rider (*"Any successor design that edits
this table must re-verify that property in the prereg text itself"*):

- `C-CONFIRM` requires `C`; `X-COLLAPSE` and `P-BLIND` both require `¬C`.
  ⇒ `C-CONFIRM` is disjoint from both.
- `X-COLLAPSE` requires `K`; `P-BLIND` requires `¬K`. `K` and `¬K` are exact
  complements by construction. ⇒ `X-COLLAPSE` and `P-BLIND` are disjoint.
- `B-PARTIAL` is the complement of the union of the other three.

⇒ **exactly one branch matches every possible read, and the match does not
depend on the ordering.** Precedence is presentation, not semantics. (This is
the defect the pricing run's original branch 3 had and its §4.4-A amendment
repaired; it is not repeated here.)

### 4.2 The two pre-registered statistics, side by side — mandatory on every branch

The read-out MUST print, for **both** judges on the **same** positions, the
complete pricing-readout table: `S1a σ²_arm` (discriminable and `all`),
`S1b` cross-fit gap `G`, `S2 headroom_J4` (discriminable, `all`,
`zeros_strict`), `S2b` leaf regret, the parity-swap diagnostics, the audit-only
naive companions with their never-quoted label, and the §4.3 bound chain in
pts and elo with the ÷3.2 / ÷5.23 bracket and the σ_game sensitivity — plus,
for each, the ratio OOF/IF. Per-stratum (`e4`, `selfplay`), per-profile,
per-phase and capped/uncapped cuts are emitted beside the pooled read and are
labelled underpowered; **no branch is ever adjudicated on a cut.**

### 4.3 Also mandatory on every branch

1. **The pricing §5 sign check, unchanged**, in the E4 autopsy's taxonomy:
   `agreement_rate`, exact two-sided binomial `p`, each judge's own aggregate
   sign, and the verdict string CORROBORATES / PARTIAL / NO CORROBORATION —
   printed **beside** the autopsy's committed benchmarks (**80% at p 0.0012 =
   corroboration; 61.9% at p 0.38 = not**) and beside the autopsy's own Tier-1
   result (**62.1% at p 2.8e-05, aggregate sign NEGATIVE ⇒ PARTIAL**) so ours
   is calibrated against a known non-corroboration.
2. `G-CAL`: the selected quartile's `n`, the sign-aligned mean, se and `z`, and
   PASS/FAIL.
3. Realized `n`, roots, phase/profile/stratum composition of what completed,
   and the fraction of the planned 502 that finished.
4. `c_tier1` (worker-s/playout) realized on the main run, and any co-tenant
   found by the process census.
5. All eight §7 integrity counters, each with its realized value.
6. The **realized 2σ resolution** of `H_OOF` in pts and in elo, and the `n`
   that would have resolved `R` to ±0.25.

## 5. What no branch does

- No branch reads the holdout.
- No branch plays a game, claims a band, writes `experiments/results.csv`,
  writes `governance/BAND_REGISTRY.csv`, or edits `governance/PRODUCTION.yaml`.
- No branch mints a claim id. (A `X-COLLAPSE` is an axis closure recorded in
  `docs/LEVER_INDEX.md` + DECISIONS; minting a claim from it is a separate
  owner decision, not this read-rule's to take.)
- No branch re-reads, re-labels or re-adjudicates the finished 2026-08-13
  pricing runs. They stand as adjudicated (branch 4, twice). This run adds a
  **scope statement** about what their ruler could see; it changes not one
  digit of what they reported.
- No branch licenses a second evaluation of anything in this directory. This
  read-rule is spent when the read-out lands.
