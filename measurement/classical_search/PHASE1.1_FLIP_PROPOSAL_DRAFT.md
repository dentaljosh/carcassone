# Phase 1.1 — PUCT-heuristic-priors vs the deep-classical champion: FLIP PROPOSAL (DRAFT)

**Status: DRAFT decision doc — PROPOSE ONLY.** Written 2026-07-06, pre-registered ahead of the n=400 confirm so it is ready when the number lands. **MEASUREMENT ONLY: nothing here changes `governance/PRODUCTION.yaml`, the champion pointer, or the v2.7/v2.9 leaf. A champion flip is *proposed*, never executed, and only after Joshua's explicit go.**

**Confirm read-out (2026-07-06 18:54): n=400, FRESH band 9.4e9, +148.2 elo (±19.0 1σ unpaired; paired z=10.17), W276/D9/L115, wr 0.701 → FIRES** (gate was +35/2σ; cleared by ~8σ). This is the official pre-registered number and the proposal is **LIVE, pending Joshua's review**. It landed *above* the winner's-curse-shrunk prediction (+60–100) — the effect is larger and more robust than the max-of-k model suggested, consistent with c1.5 being a pre-specified interior point (not a fished argmax). **K=4 n=200 same-band endgame check: running** (does the win survive the real champion endgame — result pending). Source: `measurement/classical_search/CONFIRM_PROGRESS_K2.tsv` + cell `summary.json`; `PLAN.md` pre-registered thresholds.

---

## 1. What the result IS / ISN'T

**IS** — a **self-anchored, equal-wall-clock SEARCH-ALGORITHM win** over the *current* classical champion:
- Champion beaten = `deep_classical_v29_bmild_cap8` (HeuristicMCTS, v2.9 Bmild_cap8 leaf @ h6400 + exact-K≤4 endgame handoff), the production champion of record since 2026-07-02 (`governance/PRODUCTION.yaml`; CL-041).
- Candidate = `src/carcassonne_ai/heuristic_prior_mcts.py`: PUCT + `softmax(Δleaf/τ_p)` heuristic-leaf priors + expand-all + visit-selector, plugged into the tested NeuralMCTS PUCT machinery. **Same v2.9 Bmild_cap8 leaf on both sides** — the win is *better search over the identical evaluator*, not a better evaluator.
- Screen headline (n=100, K≤2, deck-paired, equal ms/move): c1.5/τ5/visits/float @2750 sims = **+168.4 elo (paired z6.75)** vs h6400 (`SCREEN_PROGRESS_R5.tsv`; results.csv `puct_*` rows). All three 2750 c-cells fired: c1.0 +168.4/z4.85, c1.5 +168.4/z6.75, c2.5 +143.1/z5.01. The paired **Q-selector** cell at c1.5/2750 was **identical (+168.4, z6.11)** → the visit-selector effect is a low-sims artifact, moot at the deployable sims. Winner's-curse-shrunk true effect ~+90–110; confirm expected +60–100 (`PUCT_PRIORS_RESULTS.md`).

**ISN'T:**
- **Not a learned-value win.** No net. The leaf is untouched; structural blocker #2 (a *learned* component must EXCEED the heuristic) is unmoved.
- **Not an absolute-strength gain vs a non-saturated / human reference.** The comparison is in-ecosystem, self-anchored, clairvoyant matched-mode, K≤2-endgame screen (K=4 confirm pending). It says "our search wrapper was leaving elo on the table," not "we reached a new absolute tier."
- **Not a leaf/rule-scope change.** v2.7/v2.9 leaf semantics and the locked 2p Base+Farmers scope are unchanged.

---

## 2. Champion-flip PROPOSAL (propose only)

**What would change (if the confirm fires):**
- The top *classical agent* flips from HeuristicMCTS random-expansion UCT (C=3.0, no priors, one-random-child/sim) → the **PUCT-heuristic-priors agent** at equal wall-clock. Same leaf, same endgame handoff; only the search wrapper changes.
- Canonical files a flip would *eventually* touch (cite, do not edit): `governance/PRODUCTION.yaml` (`champion.id` / `agent` / `notes`) and `governance/CHECKPOINT_LINEAGE.csv` (a new agent-config row — this is a classical config, not a `.pt`). A proposed CL-041 amendment: PRODUCTION.yaml's "HeuristicMCTS … the strongest agent in the ecosystem" (line 18) would no longer be true at equal compute.

**What stays FROZEN (absent Joshua's approval):**
- `governance/PRODUCTION.yaml`, the champion pointer, and the **v2.7 / v2.9 Bmild_cap8 leaf semantics** (hash `7fc930b82801cb43`) — UNTOUCHED. This is a pure search win; the leaf is identical on both sides, so no leaf re-tune is implied.
- The candidate ships **behind its existing flag, default-OFF, bit-exact when off** (`PLAN.md` build spec) — no production-path behavior changes on merge.
- No learned-value promotion, no rule-scope expansion.

---

## 3. Ruler re-anchor scope — THE LOAD-BEARING PART

The whole strength ladder is calibrated to **HeuristicMCTS as the reference/anchor/opponent**. If it is no longer the top classical agent, every verdict below must be re-read. Two families matter differently: those where **HeuristicMCTS-as-opponent defines "the bar"** (HIGH — the bar moved) vs those anchored on the **exact solver / offline label oracle** (LOW — ground truth unaffected; only the "strongest practical ruler" phrasing needs a note).

| Doc / claim | How HeuristicMCTS is the anchor | Re-anchor need |
|---|---|---|
| **`governance/PRODUCTION.yaml`** champion + **CL-041** (`CLAIM_REGISTRY.csv`) | Deep-classical HeuristicMCTS h6400 IS the champion + reference ruler ("strongest agent in the ecosystem"). | **HIGH.** The pointer itself moves; "strongest agent" is falsified at equal compute. Propose CL-041 amendment + a `notes` re-word. |
| **`measurement/level2/LEVEL2_LADDER_VERDICT.md`** (CL-023) | `heur@800-v2.7` = "the established production ruler"; rungs heur@200/800/1600/3200; verdict "ruler NOT saturated (heur@1600 > heur@800 +55.2/z3.23)". | **HIGH.** The ladder's *top rung* is no longer the strongest classical agent; a PUCT-priors rung sits above h6400. "Not saturated" is REINFORCED (headroom confirmed above h6400) but the rung labels + top-of-ladder need re-drawing. |
| **`measurement/level2/LEVEL2_L22_VERDICT.md`** (CL-024) | iter8 placed by scoring vs heur@800/1600/3200; beats h800/h1600, LOSES h3200 (−28.7/z−0.70). | **MED.** Qualitative claim survives, but "below the deepest heuristic rung" understates it — the true top classical agent is further above iter8 than h3200 was. Re-read iter8's absolute placement. |
| **`measurement/level2/LEVEL2_HYBRID_VERDICT.md`** (CL-026) | Champion-to-beat = `heur@3200`; hybrids LOSE to it → verdict "**deep heuristic remains strongest**". | **HIGH.** "Deep heuristic remains strongest" is FALSIFIED as a classical-top claim. Re-run the strongest hybrid vs the new top agent before citing it. |
| **`measurement/level2/LEVEL2_L23_VERDICT.md` + `LEVEL2_K4_PROBE_VERDICT.md`** (CL-025) | GT anchor = **exact K≤2/K=4 solver** (non-circular); `heur@3200` = "strongest directly-tested practical ruler". | **LOW.** Exact-solver GT unaffected. Only the "strongest practical ruler" phrase needs a "superseded by PUCT-priors at equal time" note. |
| **`measurement/clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md`** (CL-022) | Fixed ruler = `HeuristicMCTS @ h800-v2.7`; both arms scored elo-vs-heur@800. | **MED — and corroborating.** Its own "selector ≈ 100–105 elo" finding (visit-argmax vs best_action) is the SAME mechanism the PUCT candidate exploits (`visits` selector = +72 vs Q). It *predicted* this win → evidence, but the elo-vs-heur@800 scale still needs re-reading. |
| **`clean_eval/CLEAN_EVAL_AUDIT.md`** (CL-001, CL-012) | **HeuristicMCTS (matched-v2.7) is THE strength yardstick / reference opponent** for every re-judged historical claim. | **HIGH.** Every "vs matched-v2.7 HeuristicMCTS" absolute is anchored to a now-non-top agent. CL-001 (learned policy beats the matched heuristic) still holds *vs that opponent*, but the absolute-strength reading shifts up. |
| **Sibling-regret / value-autopsy family** (CL-033/034/037/039/040/042 incl. M2) | `h6400_v2.9` = the **offline sibling-regret label/teacher oracle**; later reads score vs the **exact K≤2 solver**. | **LOW–MED.** These are *offline labeling* references, not game opponents — a game-search win doesn't change the labels, and the M2 KILL's solver-scored reads are unaffected. But the recurring "nothing beats the τ0.895 leaf" framing implicitly treats h6400 *search* as the ceiling — annotate that a stronger classical *agent* now exists at equal time. |
| **`reference_rodv2_iter2_eval_anchor`** (auto-memory) | RoD-v2 iter_02 ≈ h3200 as the *game-play* anchor; `h6400_v2.9` = the non-saturated *offline* ruler. | **LOW.** iter_02 ≈ h3200 shortcut unaffected. Add a note that a stronger classical agent than h6400 exists at equal wall-clock, so "h6400 = non-saturated ceiling" is now "non-saturated *among HeuristicMCTS depths*". |

**Concrete re-anchoring = (a)** re-draw the ladder top so the PUCT-priors agent is the reference rung above h6400; **(b)** for HIGH rows, re-run the key contender vs the new top agent (don't rescale by arithmetic — the win is K≤2/equal-time and winrate-vs-margin nuances differ); **(c)** for LOW rows, a one-line "strongest practical ruler superseded" annotation. This is the **Phase 3 ruler-fix** work.

---

## 4. Historical "parity with deep search" conclusions to RE-READ

Each below concluded "X ties/parities/loses-to deep classical (h3200/h6400)" — i.e. compared against the exact agent the PUCT candidate just beat by ~+168 at equal time. **The rung moved up: "tied deep classical" now means "tied an agent itself well below the classical frontier at equal compute."** Re-read (re-run the strongest contender vs the new top agent), don't blindly rescale.

- **RoD v2.8 continuation** (DECISIONS 2026-06-22; `results.csv` `rod_iter01_v28_vs_heur3200_v28_n800`): "CLOSED the equal-leaf gap to **PARITY** vs heur@3200; does NOT exceed deep search."
- **RoD v2.8 overnight flywheel** (DECISIONS 2026-06-23; `rod_ov_iter08_vs_heur3200_v28_n800`): iter_08 = "**heur@3200 parity**, does not exceed" (well-powered TIE, n=800).
- **RoD2 v2.9 flywheel autopsy** (CL-029; `rodv2_*_vs_heur{3200,6400}_v29`): chain "sits at ~**h3200_v2.9 parity**, LOSES to h6400_v2.9 (−22..−32)".
- **L2-2** (CL-024; `l22_iter8_vs_heur3200_b310_n400`): iter8 vs h3200 = −28.7, "edge ERASED by the deepest heuristic rung."
- **Hybrid handoff** (CL-026; `l2hyb_K{5,8}h3200_vs_heur3200`): hybrids LOSE to heur@3200 → "deep heuristic remains strongest."
- **Deeper-search ruler probe** (DECISIONS 2026-06-24; `deepsearch_rod1_vs_h6400_v28_n200`): "RoD1 LOSES to h6400 → h6400 = the non-saturated REFERENCE the program needs." — the reference this proposal displaces.
- **Exact-endgame hybrid** (`exact{2,3,4}_vs_heur3200_v28`): exact endgame "EXCEEDS heuristic on margin but OUTCOME-NEUTRAL" — a margin, not winrate, edge vs the same deep-heuristic bar.
- **Odometer residual** (`odometer_residual_s025_h3200_n120`): "net still LOSES to heur@800+; ceiling raised ~1 doubling, not broken."

**Caveat for the re-read:** the PUCT win is at EQUAL WALL-CLOCK, K≤2, clairvoyant matched-mode; several parity verdicts were winrate-vs-margin split. Re-anchoring means re-measuring the top contenders against the new agent, not a global elo shift.

---

## 5. Downstream (STATE, do not action)

- **Phase 1.2 (ID-alpha-beta):** the gate that made 1.2 conditional ("1.1 fires") is now met — 1.2 is worth doing (`PLAN.md` decision tree; `PUCT_PRIORS_RESULTS.md` implications #3). Surface go/no-go + cost to Joshua before launching.
- **Phase 5 (Gumbel) warm-start:** the distillation/warm-start source becomes **this winner**, not h6400 HeuristicMCTS.
- **Phase 3 ruler-fix:** promoted to higher priority — the ruler ladder is calibrated to the HeuristicMCTS this beats (Section 3 is the scope).

---

*Cites: `governance/PRODUCTION.yaml`, `governance/CLAIM_REGISTRY.csv` (CL-001/012/022/023/024/025/026/029/041/042), `governance/CHECKPOINT_LINEAGE.csv`, `experiments/results.csv` (`puct_*`, `rod*_vs_heur*`, `l22_*`, `l2hyb_*`, `deepsearch_*`, `exact*`, `odometer_*`), `measurement/classical_search/{PLAN.md,PUCT_PRIORS_RESULTS.md}`, `measurement/level2/*VERDICT*.md`, `measurement/clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md`, `clean_eval/CLEAN_EVAL_AUDIT.md`, auto-memory `reference_rodv2_iter2_eval_anchor`. Numbers are pointers to those files, per the point-don't-copy rule.*
