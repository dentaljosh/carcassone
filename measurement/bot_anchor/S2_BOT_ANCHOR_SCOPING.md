# S2 — Out-of-ecosystem bot anchor: scoping + recommendation

**Status:** SCOPING (no port yet) · **2026-07-01** · Plan: [docs/POST_REVIEW_PLAN.md](../../docs/POST_REVIEW_PLAN.md) §1 S2
**Goal:** port ONE external opponent to break the **v2.x-family circularity** (F4/F9: every internal number is
scored against the v2.7/v2.9 leaf or an oracle 0.995-correlated with it) and give M1–M3 + the ship stack a
**non-circular external reference.** Bot-only this week (humans deferred). Even a weak-but-independent bot anchors
the ladder; strength is secondary to independence.

## The three candidates (scoped via GitHub, no cluster spend)

| | **SamuelScheit/carcassonne-ai** | **33fred33/CarcassonneAI** (Ameneyro 2020) | **tiborcamargo/Carcassython** |
|---|---|---|---|
| Agent | **MuZero** (muzero-general fork) — learned dynamics+value+policy | vanilla MCTS + MCTS-RAVE + Star2.5 (academic) | RL framework/scaffold (agent maturity unclear) |
| Independence from our leaf | **HIGH** — different algorithm family (MuZero self-play, learned model), different author/data; zero contact with our v2.7/v2.9 leaf | HIGH — classical MCTS-RAVE, own heuristics | Medium — RL scaffold, likely trained similarly to AZ if at all |
| Engine | **wingedsheep** (the SAME base we vendored: `carcassonne_game_state.py`, `objects/farm.py`, `utils/points_collector.py`, `base_deck.py`) | its own `Carcassonne_Game` engine | its own 71×71 numpy engine |
| Scope | 2-player (`players=range(2)`); base/river/I&C decks present | Carcassonne (meeple rules present; farmer detail unconfirmed) | custom; RL-oriented |
| Pre-trained weights | **YES** — `src/results/carcassonne2/2021-11-03--*/model.checkpoint` (2.38 MB ×2) | none shipped (would train/tune) | none obvious |
| License | subdir **MIT** (repo top-level GPL-2.0; the muzero code is MIT) | **none specified** (⚠️ all-rights-reserved by default) | (unconfirmed) |
| Runnable | muzero-general framework; inference needs only **torch+numpy** (ray/tensorboard/nevergrad are training-only) | research-focused; pygame UI + notebooks | framework + Tkinter GUI |
| Port effort | **LOW–MED** (shared engine → action/state semantics align; ray-free inference extraction) | MED–HIGH (own engine bridge + no license) | HIGH (own engine, unclear agent) |

## Recommendation: **SamuelScheit/carcassonne-ai (MuZero)**

It is the only candidate that is simultaneously (a) a genuinely **independent learned agent** (MuZero — maximal
non-circularity vs our AZ+v2.7-leaf), (b) **pre-trained** (weights shipped → zero training spend), (c) built on the
**same wingedsheep engine** (bridge is glue, not a reimplementation), (d) **runnable** (a known framework), and
(e) **MIT** (clean for internal use). 33fred33 is the classical backup if we later want a non-learned anchor, but it
costs an engine bridge + a license ask. Carcassython is deprioritized (own engine, unclear agent).

### Port plan (~1–2 days, bounded)
1. Isolated venv: `torch`, `numpy` only (skip ray/tensorboard/nevergrad — inference-only).
2. Load `model.checkpoint` into `models.py` `MuZeroNetwork`; reuse the MCTS in `self_play.py` + `carcassonne2.py`
   (the muzero-general `Game`: `reset`/`step`/`legal_actions`/`to_play`, `observation_shape`, `action_space`).
3. **Cross-engine match bridge** — both engines are wingedsheep-descended, so tile/meeple action semantics map.
   Run matches with our engine authoritative; translate each state → SamuelScheit's observation for its move, map
   its chosen action back to our action space (or vice-versa). Fair-information, deck-paired.
4. **Sanity gate FIRST (cheap, kills fast):** SamuelScheit-MuZero vs random over ~50 games. If it does **not** clearly
   beat random, it is not a useful anchor (a 2021 seminar MuZero, 2.38 MB net, may be weak) → fall back to 33fred33
   or report "no clean anchor landed" (the brief's explicit allowance). If it beats random, ladder it vs
   deep-classical / h6400 / the promoted stack, n≥400.

### Risks to hold
- **Strength unknown** — small net + brief 2021 training may be weak. Weak is still a valid *independence* anchor
  (confirms external strength ordering), just low-resolution. The vs-random gate decides whether it's worth the full
  bridge before we invest.
- **Cross-engine bridge correctness** — must verify action/state translation is faithful (a fuzz check: round-trip a
  state through both engines and confirm identical legal-action sets) before trusting any match number.
- **GPL-2.0 at the repo root** — the muzero subdir is MIT; keep the port isolated to the MIT code; flag before any
  distribution (internal research use is fine).

## Sources
- [SamuelScheit/carcassonne-ai](https://github.com/SamuelScheit/carcassonne-ai) (MuZero, wingedsheep engine, MIT subdir, archived 2023)
- [33fred33/CarcassonneAI](https://github.com/33fred33/CarcassonneAI) (likely F. Valdez Ameneyro's code; MCTS-RAVE)
- Ameneyro, Galván-López, Kuri-Morales 2020, "Playing Carcassonne with Monte Carlo Tree Search" ([arXiv:2009.12974](https://arxiv.org/abs/2009.12974))
- [tiborcamargo/Carcassython](https://github.com/tiborcamargo/Carcassython)
