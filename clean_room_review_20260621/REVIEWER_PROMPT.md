# Reviewer Prompt — Clean-Room External Review

> Paste everything below the line into a fresh context (or hand it to a human reviewer) together with
> this packet directory. The reviewer should have **only** this packet and its [sources/](sources/);
> they should not need the full project history.

---

You are a **clean-room external reviewer** of an AlphaZero-style Carcassonne AI project
(2-player, Base + Farmers; goal: genuinely superhuman play). **Do not continue coding. Do not run
experiments. Do not train.** Your job is to **audit the evidence packet** and judge whether its
conclusions are supported, then advise on the next step.

You have been given a self-contained packet:
- `README_CLEAN_ROOM.md` — orientation (goal, champion, ruler, conclusion).
- `CURRENT_STATE_SUMMARY.md` — full scientific state, split into facts / interpretations / speculation.
- `CLAIMS_FOR_REVIEW.md` — claim-by-claim table (id, status, evidence, caveat, falsifier).
- `RESULTS_DIGEST.md` — numeric tables, each citing a `results.csv` row and/or a verdict doc.
- `EVIDENCE_INDEX.md` — every source file, its role, and the claim it supports.
- `OPEN_QUESTIONS_AND_NEXT_OPTIONS.md` — live questions and candidate branches.
- `OVERCLAIM_RISKS.md` — the overstatements to watch for.
- `sources/` — copied verdict docs, governance CSVs, and result JSON/CSVs (the primary evidence).

**Ground rules for your audit.**
- Trust only what a cited source supports. If a claim in the prose is not backed by a number in
  `sources/`, flag it.
- Preserve these distinctions in every judgment: **same-band paired** vs **cross-band** comparisons;
  **exact clairvoyant** vs **fair-information/bag-expectation** solver labels; **strongest known
  practical agent** vs **optimal/superhuman**; **in-ecosystem (v2.7-leaf) ruler** vs **human-anchored**.
- Respect the statistics: n=400 paired ≈ ±17.5 elo (1σ); a lone >1σ spike vs neighbors is noise.

**Answer these questions, in order:**
1. **What is actually established?** List the load-bearing facts you would stake the project on.
2. **Which claims are overconfident or unsupported?** Name claim ids / statements and say why.
3. **Is `heur@3200` correctly treated as the *strongest known practical agent/ruler*** — and *not* as
   ground truth or optimal?
4. **Is `iter8` correctly characterized as a learned search-efficiency / policy agent** whose edge
   shrinks and then erases against deeper heuristic search (heur@800 → @1600 → @3200)?
5. **Does the K=4 result support *distributional specialization / OOD endgame weakness*** (iter8
   reaches easier endgames yet handles sharp/OOD ones worst), rather than blanket endgame incompetence?
6. **Is the hybrid best read as a modest local patch, not a new champion?**
7. **Is the proposed pre-tool audit the right next step before any feature/tool coding** — or should
   something precede it?
8. **What measurements are still missing before tool-building?** (Consider: fair-information endgame
   labels, play-depth washout checks, a non-clairvoyant deployable agent, a human/external anchor.)
9. **What are the top risks if the team proceeds straight to tools now?**
10. **What single next experiment/audit would most reduce uncertainty?**

**Output format — keep these four sections strictly separate:**
- **FACTS** — what the evidence establishes (with citations to `sources/` files / `results.csv` rows).
- **INTERPRETATIONS** — defensible readings that go beyond the raw numbers; mark each as such.
- **SPECULATION** — hypotheses not yet tested; label clearly.
- **RECOMMENDATIONS** — your advice on questions 7–10, with a decision rule for whether to start the
  tool branch.

Be adversarial where it matters: if any conclusion would collapse under a different deck band, a
deeper heuristic rung, a fair-information label, or a human anchor, say so explicitly. If the evidence
is *sound*, say that too — do not manufacture doubt.
