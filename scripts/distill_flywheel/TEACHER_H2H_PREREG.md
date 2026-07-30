# TEACHER H2H — PRE-REGISTRATION: CL-067 net@2752 vs the champion@11008 (band 94e9)

> **STATUS: PRE-REGISTERED 2026-07-30 ~01:35, FUNDED, band 94e9 claimed. Committed BEFORE the
> first game of the cell.** Promotes
> [PROPOSED_TEACHER_H2H_CELL.md](PROPOSED_TEACHER_H2H_CELL.md) (`eaf900f`) to a prereg on
> Joshua's 01:25 direction — verbatim: *"maybe we should run the eval first."* This cell now runs
> **BEFORE** the rest of the rodv3 flywheel turn; turn-1 gen is stopped at 33 banked games and
> becomes premise-gated background work.
>
> **What this is:** the direct measurement of the pair every derivation has had to route around.
> It prices the rodv3 **premise**. It is NOT the turn-1 gate (which measures the *derivative* and
> remains NOT funded), not a strength lever, and not a promotion proposal.

## The question

The rodv3 awakening premise got paraphrased as *"the operator beats its teacher at 2752."* The
measured fact is narrower: net+search@2752 beats the **same-budget classical** champion@2752
(**+35.7 ± 12.3**, CL-067, bands 52e9+56e9 pooled). The net's actual **corpus teacher** ran at
**k8×1376 = 11008** (`distill_strong_20260723/iter_03/manifest.json` → `config.teacher`,
`net_mode: "net-free (champion)"`). Against *that* player the net is **UNMEASURED in either
direction** — no `results.csv` row holds the pair.

**Two cross-band derivations give OPPOSITE SIGNS**, which is the whole reason to measure it:

| route | direction | why it is not a measurement |
|---|---|---|
| via CL-060's budget-only cell (+49.85 for k8×1376 over k4×688, band 32e9) | net lands **~+8 ABOVE** its teacher | transitive through a shared baseline, across bands |
| via CL-067's `counterevidence` equal-cost argument (49.85 − 35.7) | net lands **~14 BELOW** its teacher | same maneuver; the "+14.1" is DERIVED, and collides arithmetically with an unrelated +14.1 in `best_evidence` (see the rodv3 prereg's correction note) |

Both are the transitive-through-a-shared-baseline move that the buried-caveats audit's F2
documents **inverting a +50 contrast**. Only a direct head-to-head settles it. House practice also
says inflate σ 1.5–2× on any cross-band z in this family (band-level over-dispersion, CL-068
amendment) — which is exactly what makes both derivations unsafe to act on.

## Cell design (all values final at commit time)

| knob | value |
|---|---|
| **candidate** | CL-067 net-prior fair agent — `distill_strong_20260723/ckpt/iter_03.pt` POLICY priors + **FROZEN** curve125 leaf (value severed), `k_dets 4 × sims 688 = 2752`, `net_backend` torch via carc-orch SHM on local |
| **opponent** | the PRODUCTION champion `puct_priors_v29_bmild_cap8` / `FairHeuristicPriorAgent` at its **promoted** `fair_deploy` budget **`k_dets 8 × sims_per_det 1376 = 11008`** (`governance/PRODUCTION.yaml`) |
| asymmetry mechanism | harness env `OPP_K_DETS=8 OPP_SIMS=1376` → `--opp-k-dets/--opp-sims` (the sibling axes; `--opp-sims` alone cannot express a k-change). **Proven at exactly this budget by CL-060**, whose candidate arm was k8×1376 vs the then-k4×688 champion |
| shared knobs | `c_puct 1.5`, `tau_p 5.0`, `value_norm 15`, `leaf_quantize float`, `final_select visits`, exact endgame `--exact-k 2`, both sides leaf `a36d2e15a3b3d71d` (harness dialect) |
| n | **400 deck-paired** (200 decks), **fresh band 94e9** (claimed in `BAND_CLAIMS.txt`; chosen by enumeration — 22/24/26/28/32/44/46/52/56/72/74/76/78/80/82/84/86/88/92e9 are burned or claimed, 99e9 is pre-flight scratch and never harvested) |
| statistics | paired elo **and** deck-paired margin, **both reported**; sign agreement required for any claim. Reporting only the statistic that clears is how three overturned findings here got their start |
| harness | `scripts/classical_search/fair_net_vs_net_orch.sh --info fair-netprior --opponent fair-champion`, `--shared-claim --no-results-csv` |
| out | `/mnt/c/carc-shared/teacher_h2h_94e9/` |

### ⚠️ Cost asymmetry is the point, and it is NOT a confound here

This is a deliberately **unequal-budget** cell: it asks whether the net at ¼ the compute matches
the tier that taught it. The opponent is ~4× the candidate's search. Two consequences to state
before any number exists:

- **The champion's `parallel_workers: 8` buys nothing here.** An eval farm is *game*-parallel, so
  each game's champion runs **sequentially** at 11008 ≈ **13.76 s/move**, not the 2.1595 s/move
  desktop-profile figure (CL-071's own "eval cost quadrupled" warning). Any cost estimate using
  2.16 s/move is wrong by ~6.4×.
- **A cost-ratio guard is meaningless for this cell** and will not be used as a gate. The
  *deployability* question is CL-067's, already answered NEGATIVE, and is not reopened here.

### ⚠️ The harness's "NOT the shipped production champion" warning is STALE — ignore it, and fix it later

The launch log emits:

> *"--opponent fair-champion: the search config deviates from governance/PRODUCTION.yaml
> (k_dets=8 (production 4); sims=1376 (production 688)) … the opponent is **NOT** the shipped
> production champion — do not report this cell as 'vs production'."*

**That warning is wrong here, and it is wrong for a reason worth fixing.** Despite its text, the
check does **not** read `governance/PRODUCTION.yaml`. It compares against a **hardcoded constant**
in `scripts/classical_search/eval_fair_puct.py`:

```python
PROD_KNOBS = {"c_puct": 1.5, "tau_p": 5.0, "leaf_quantize": "float",
              "value_norm": 15.0, "k_dets": 4, "sims": 688}     # ← pre-promotion
```

`k_dets: 4, sims: 688` is the **pre-promotion** deploy budget. CL-071 promoted the champion to
**k8×1376 = 11008** on 2026-07-29 and this constant was not updated, so the guard is now
**inverted**: a cell run at the *actual* champion budget is flagged as deviating, while a cell at
the superseded k4×688 is silently blessed as "production". The opponent arm of this cell **is** the
champion of record.

**No measurement is affected** — the budgets actually searched are exactly the ones passed on the
command line, and the manifest records them. This is a provenance/warning-text defect only. It is
**not fixed in this commit**: `eval_fair_puct.py` is main-tree source and a cell is live, so the
edit waits for a quiet window (house rule). Filed here so the next reader does not trust the
banner — and so nobody "corrects" this cell's opponent back to k4×688 on the strength of it.

## Pre-registered read-out (fixed before the first game)

Let `elo` be the candidate's paired elo vs the champion@11008, with 1σ ≈ ±17.4 at n=400
(±12-ish only under favourable pairing; do not assume the better figure).

- **PREMISE STRONG — `elo ≥ 0` with sign agreement:** the operator produces data **at or above
  its own corpus tier at ¼ the compute**. The flywheel premise holds in its strong form; turn-1's
  gate reads cleanly; the gen@11008 escalation becomes a debate from evidence.
- **PREMISE WEAK — `elo < 0` with sign agreement:** the awakening premise narrows to *"above
  same-budget classical only."* Gen at the corpus-teacher budget becomes the **only** clean
  lever-6 test, and a DEAD turn-1 gate is **expected rather than informative**. This is the
  outcome that *saves* ~29 h local-only of gen@11008 spent on a hunch.
- **BRACKET-NARROWING, NOT A VERDICT — `|z| < 2`:** the two derived candidates (≈+8, ≈−14) both
  sit near 1σ, so an underpowered read cannot separate them. **Pre-committed extension: if
  `|elo| ∈ [5, 25]`, extend the SAME cell to n=800 on fresh decks of the same band, then verdict.**
  Outside that interval a `|z| < 2` result is reported as inconclusive without extension.
- **Sign split** (elo and margin disagree) at `|z| < 1` → inconclusive; no claim, no funding move.

**Nothing is promoted by this cell in any branch.** `governance/PRODUCTION.yaml` is untouched;
the champion of record does not move on a premise measurement.

## Pre-flight (mandatory, per the house rule — production knobs, only game count differs)

10 games at the **exact** cell configuration (same sims, k_dets, opp budget, leaf, exact-K,
orch-or-not, W), on pre-flight scratch seeds (`99e9`, never harvested). Verify **measured
per-move cost for BOTH arms** against this doc's expectations before committing the box to the
full run, and set the eval `OW` from what the smoke supports. Linear extrapolation from a cheaper
smoke is not permitted here: per-leaf cost grows with game length, and the opponent's cost is the
dominant term.

## Ops

`nice -n 19`, `setsid … </dev/null &`, `OMP_NUM_THREADS=1` to the orch **server**,
orch `max_batch ≥ OW`, `--shared-claim` (a second box may join after a bundle sync). Watchdog
armed on-box keyed on this cell's **record glob** (`seed*_a*.json`), not on npz — and note the
eval path fails **OPEN**: a short cell writes a plausible `summary.json`, so verify `n` equals 400
before reading any number (memory `feedback_shared_claim_orphan_stall`).

## Relationship to rodv3 turn 1

Turn-1 gen is **stopped at 33 banked games** (`rodv3_turn1/iter_04`, claims cleaned to parity,
resumable losslessly via `--shared-claim`). The laptop continues that pool as background work at
its own W\*. The turn-1 **gate stays NOT funded**; this cell's answer decides the morning menu.
