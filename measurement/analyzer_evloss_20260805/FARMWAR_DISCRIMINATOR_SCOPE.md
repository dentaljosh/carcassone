# Farm-war discriminator — scoping note (UNFUNDED; Joshua's call)

**Status: SCOPED 2026-08-05 late night, not funded, nothing built.** The question it decides
comes from readout §6c: when Joshua's contested-farm-war moves grade as blunders under the
champion's own leaf, **are they actually worse — or is the leaf mis-pricing farm wars?**
Six-game evidence motivating it: farms 6-for-6 Joshua; champion 11.0 farm pts/seat vs him
against 20.5 in its own corpus (0 in g6 = its own p5); his ΔQ concentrated in tile placement;
his two wins among his three worst-graded games.

## Design (adapts the proven oracle-pilot pattern, `oracle_score_pilot.py`)

Per selected ply: take the position, the move he PLAYED, and the move the champion's search
PREFERRED (both already in the EV-loss artifacts — `action_played` / `action_best`). Score
BOTH continuations under M CRN-paired deck completions (same world seeds both arms — the
pilot's `world_seeds`/`position_delta` machinery), playing both seats forward with the same
continuation agent. Report `V(played) − V(best)` in **final-score points**. A positive mean
on the farm-war stratum = the "blunders" out-earn the champion's picks = the leaf mis-prices
farm wars. Sign is the deliverable; magnitude is a bonus.

- **Sample.** The high-ΔQ human plies from the six graded games, stratified: (a) the
  farm-war stratum — g5's 12 blunder plies + g6 ply 44 + the g3 blunder set (~20–25 plies);
  (b) a CONTROL stratum of non-farm high-ΔQ plies of similar ΔQ magnitude (~15 plies), so the
  verdict is "farm wars specifically" vs "his style generally". Total ~40 positions.
- **Judge.** The pilot's judge family question applies with full force: an in-family judge
  (clair-PUCT over the same leaf) is structurally suspect HERE — it shares the leaf under
  test, so it's biased *toward* the champion's picks; a positive result through it is
  therefore CONSERVATIVE (extra credibility), a null through it is uninformative. Run the
  in-family judge as primary (cheap, precedented) + the Tier-1 out-of-family judge
  (`--oracle-policy tier1-greedy` precedent) as the sign check, exactly the 2026-07-28
  discriminator pattern. ⚠️ Tier-1 is 1.83× noisier and has no curve125 — sign only.
- **Cost.** The pilot ran 100 positions × M=32 in ~81 min at W16 local. 40 positions ≈
  **~35 min at W16**, double for the second judge ⇒ **~1–1.5 h local, one evening, no cloud**.
- **Power.** The pilot's measured per-position sd (~2.4 pts at M=32, between-position floor
  ~1.5) ⇒ at n≈25 farm-war plies, detectable effect ≈ 1σ at ~0.5 pts/move, 2σ at ~1 pt/move.
  The effect implied by the ledger (champion −9.5 farm pts/game vs its own norm, spread over
  a handful of contested plies) would be **~2–4 pts/ply — comfortably detectable if real.**
- **Positions replay** via the archives' `(deck_seed, actions)` under each game's OWN rules
  profile (the corrected resolver). fixed_v1 positions need the R9 env — the EV-loss
  `prepare_env` handles it.

## What each outcome means

- **Farm stratum positive, control ~0:** a measured, human-found hole in the champion leaf's
  farm-war pricing. First evaluation defect localized by E4 play; feeds C5/C7 re-tune
  machinery (farm terms exist in the leaf and are sweepable). Also retroactively re-labels
  his g5 "12 blunders".
- **Both strata ~0 or negative:** the leaf prices his moves fairly; the champion's picks
  really are better; the wins were deck-assisted. His coaching takeaway = the ΔQ readouts
  stand as written.
- **Both positive:** general same-family self-preference in the grader, bigger than the
  pilot's +0.74 — a statement about the instrument, gates future grader claims.

## Why not now

E4 n=6 is thin, the boxes are idle but it's a Joshua-funding call under the house rule (≥30 min
compute), and the sample doubles for free with every game he plays. Bar to fund: his call, or
the farm streak surviving 2 more games (8-for-8 would put the champion's farm shortfall past
2σ on its own corpus sd).
