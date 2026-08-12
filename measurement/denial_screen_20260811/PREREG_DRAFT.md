# TARGETED-DENIAL DOSE SCREEN — PRE-REGISTRATION (DRAFT)

> **STATUS: 📝 DRAFT — BUILT, NOT AUTHORIZED, NO BAND CLAIMED, NO GAMES PLAYED.**
> The orchestrator reviews this draft; Joshua authorizes any launch. **TODO (launcher,
> not this document): claim ONE fresh band in `governance/BAND_REGISTRY.csv` before
> game 1** — this draft deliberately claims none.
>
> Term build: `src/carcassonne_ai/flat_leaf.flat_denial_term` + the Rust
> `carc_core::leaf::denial_term` (2026-08-11; LEVER_INDEX "targeted denial",
> BACKLOG 2026-05-16 item 3). Parity gate:
> `scripts/rustport/reconcile_leaf.py --configs denial` — **PASS, 81,932 values,
> 0 mismatches** (golden + midgame-300 + panel; denial cells bite on 8.4% / 16.4%
> of values). Flag-off is byte-identical (golden gate green; champion hashes
> `a36d2e15a3b3d71d` / `158f17ff76adaa02` / `6dfffd57051690f2` unchanged).
> Free evidence read first: `scripts/classical_search/denial_e4_replay.py`
> (see §E4 gate below).
>
> Conventions parent: [capscurve PREREG](../capscurve_resweep_20260803/PREREG.md) ·
> instrument precedent: [LEVER_MENU_PLAN §4.4](../../docs/LEVER_MENU_PLAN_20260810.md)
>
> **Nothing in `governance/PRODUCTION.yaml` is touched by this document or this run.**

## The question

The v3 **blanket** asymmetric opponent cap died (C5 cells null; the 2026-08-03
`fixed_v1` re-sweep confirmed `oppcap4`/`oppcap12` null at ~35-elo paired resolution).
The lit-review reframe (BACKLOG 2026-05-16 item 3) says the principle wasn't wrong,
the functional form was: denial value is **targeted** — sabotaging an opponent's
**near-complete large** city ≈ halving its projected payout. The champion leaf prices
opponent anticipation through a term **capped at `opp_bonus_cap` = 8**, so no
opponent city, however large and however close to closing, can ever be worth more
than 8 points of fear — the champion won't spend a tile to block where a strong
human would (E4 record: farms + big-feature denial are where Joshua out-plays it).

**Does an uncapped, targeted denial term — fired ONLY on opponent-strict-majority
incomplete cities with `city_root_delta >= 8` and `0 < open_n <= 2` — buy strength
at plausible doses?**

## The term (as built — semantics of record)

For each qualifying opponent city the leaf subtracts, from the evaluating player's
POV, `denial_dose * (city_root_delta - denial_size_min + 1)` — linear escalation,
1 point of extra fear at the size threshold — **on top of** the existing capped
anticipation and **explicitly NOT subject to `opp_bonus_cap`** (escaping that cap
for the large∧near-complete conjunction is the entire point). Tied cities never
fire; own cities never fire from the owner's POV; `open_n == 0` (D16 unclosable)
never fires. Full contract: `tests/test_denial_term.py`.

## What this run is NOT

Not a promotion. A positive cell at n=200 is a *finding to top-up/confirm*, never a
production change. The valuable cheap outcome is the **screen-level null** — "no
dose in the plausible range moves the champion at ~35-elo resolution" — which kills
the lever's cheap form and sends it back to mechanism work.

## Design

**One axis (dose), three cells, one shared fresh band (CRN).** Candidate = the
champion leaf + denial at dose d (thresholds at the built defaults `size_min 8`,
`open_max 2`); opponent = the intact production champion. Both sides `fixed_v1` +
R9, `--backend rust`, the **2750 ablation instrument**
([`eval_puct_priors.py`](../../scripts/classical_search/eval_puct_priors.py) via
[`capscurve_resweep_launcher.sh`](../../scripts/classical_search/capscurve_resweep_launcher.sh)
— reuse, do not rewrite), `--cand-sims 2750` both sides.

| # | cell | `--cand-leaf-json` | candidate leaf hash | axis |
|---|---|---|---|---|
| 1 | `denial0.5` | `{"denial_dose": 0.5}` | `e42e5b4fa90c6720` | half-strength dose |
| 2 | `denial1.0` | `{"denial_dose": 1.0}` | `b80f7673fd5abc17` | 1 leaf-point per escalation point |
| 3 | `denial2.0` | `{"denial_dose": 2.0}` | `13611b9b90ed8096` | double — brackets the axis above |

Champion side is env-`DEFAULT_CONFIG`, hash **`a36d2e15a3b3d71d`** (recomputed
2026-08-11 under the denial build — unchanged, additive fields excluded at default).
All three candidate hashes are distinct from it and from each other.

- **Sign convention:** elo / margin is **candidate − champion**. Positive = denial
  helps at that dose.
- **Deck-paired**, same deck both colours. **n = 200** per cell (100 decks × 2 seats).
- **One fresh band for all three cells (CRN)** — every cell plays the same 100 decks
  against the same intact champion; every contrast is within-band deck-paired, the
  robust class. **Band: TODO — claimed by the launcher at launch, never here.**
- Doses are pre-registered; **no post-hoc dose insertion** — a promising-looking
  in-between dose is a new prereg, not an extra cell.

## Primary statistic & branch map (house standard)

**Primary: each cell's deck-paired margin z** vs the incumbent on the shared band
(the robust within-band class; elo alongside for readability, never primary).

- **|z| ≥ 2.0** → resolved at screen level: positive → top-up/confirm per the n=800
  precedent (LEVER_MENU §4.4) before ANY further claim; negative → the dose hurts,
  cell closed.
- **1.5 ≤ |z| < 2.0** → top-up that cell (n→400 paired) on the same band, once.
- **|z| < 1.5** → null at screen resolution; close the cell.
- All three null → the cheap form of the lever is dead; LEVER_INDEX row flips to
  TRIED-NULL with this prereg as pointer. Falsifier for the closure = a mechanism
  change (different escalation form / search-level denial), **not more n**.

## Power (stated so the null can't be over-read)

n=200 deck-paired ≈ **±35 elo at 2σ** (house table + capscurve realized σ). This
screen resolves a large effect only; a ≤20-elo true effect is NOT excluded by a
null here and must not be written up as flat.

## Wiring gates (before game 1)

1. `scripts/rustport/reconcile_leaf.py --configs denial` — **already PASS**
   (2026-08-11, 0/81,932 mismatches incl. the dose-0 identity control on 3 legs).
2. `gate_eval_puct_priors_backend.py --games 4 --cand-sims 2750 --opp-sims 2750
   --exact-k 2 --workers 4 --cand-leaf-json '{"denial_dose": <d>}'` per cell under
   the launcher env (the F7b wiring-identity pattern): `--backend rust` must play
   the same games as `--backend python` on the denial leaf.
3. Manifest check per cell: candidate leaf hash matches the table above; champion
   side `a36d2e15a3b3d71d`; `fixed_v1` + `r9_env_ok` both sides.
4. `_assert_cy_float_path` WARNS (not raises) on denial — expected; the cells run
   `--backend rust` where no Python leaf is computed.

## The E4 gate (free evidence, runs BEFORE authorization)

`scripts/classical_search/denial_e4_replay.py` replays the E4 archives and re-runs
the champion's own search (CRN) with and without denial at the screen doses. If the
term flips ~0 champion picks per game at dose ≤ 1.0, the screen is measuring a term
the search will almost never express — expect null, question whether dose 2.0 alone
is worth the compute, and say so in the authorization ask.

## Decision map (what each outcome buys)

| outcome | action |
|---|---|
| all null | cheap lever dead; LEVER_INDEX → TRIED-NULL; no further denial leaf work without a new mechanism argument |
| any cell z ≥ +2 | top-up → n=800 confirm on a fresh band (never promote from the screen) |
| any cell z ≤ −2 | denial at that dose HURTS — informative for the mechanism (over-fear); close |
| mixed | dose-response read across the 3 rungs (the trend is the measurement), then confirm the best rung only |
