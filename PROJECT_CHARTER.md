# PROJECT CHARTER — Carcassonne AI

> **Strategic thresholds marked `TBD-Joshua` require Joshua's ratification before they bind.** This charter
> sits in the **DECISIONS** layer of the governance spine (see `governance/README.md`). It points to the
> live context rather than restating it: read [`CLAUDE.md`](CLAUDE.md) (goal change + the two structural
> blockers), [`docs/ORIGINAL_PROMPT.md`](docs/ORIGINAL_PROMPT.md) (the original analyzer win-condition this
> goal now overrides), and [`DECISIONS.md`](DECISIONS.md) 2026-05-28 "Goal change". Claim ids below resolve
> in [`governance/CLAIM_REGISTRY.csv`](governance/CLAIM_REGISTRY.csv).

---

## The two tracks (do NOT silently merge them)

This project currently contains two distinct efforts that are easy to conflate. The charter's first job is
to keep them apart; its second is to flag that **which one is primary is currently unresolved** (below).

**Track A — Strong verifiable agent (production-oriented).**
Strongest learned **policy** wrapped around the hand-crafted **v2.7 `virtual_score`** search leaf. The agent
is PUCT search over a human-designed heuristic; the net contributes priors (and, candidate, a residual value
head). This is **where the current validated gains live**: iter_11 **+89.7** elo and the residual net **+83.2**
elo, both *in-ecosystem* vs our own matched-leaf HeuristicMCTS yardstick (CL-001, CL-002). Production-oriented:
ship the strongest thing we can *verify*, even if its strength is heuristic-bounded.

**Track B — Genuine self-improvement (research-oriented).**
A **learned value** that participates in AND improves the search teacher — an AlphaZero/KataGo-style climbing
curve where strength compounds across iterations because the learned component *exceeds* the heuristic leaf.
**Current status: NOT demonstrated.** Blocked by the two structural walls from `CLAUDE.md`:
1. **Measurement** — no strong, non-saturated, out-of-lineage / human-anchored reference exists yet (Tier-1 is
   saturated; self-anchored elo can climb while absolute strength regresses). We cannot currently tell whether
   we are approaching the goal.
2. **Leaf ceiling** — the v2.7 leaf caps learned strength near strong-human *by construction* (CL-010); the
   learned components do not yet exceed it.
   Plus: the Lever-3 residual flywheel was **NULL for compounding** (CL-011 *Disfavored*) — iter0 best, iter1
   regressed, iter2 tied within noise. No demonstrated AlphaZero flywheel.

Track A can succeed (ship a strong heuristic-bounded agent) while Track B remains entirely undemonstrated.
They are not the same project and must not be reported as one.

---

## Primary objective — CURRENTLY AMBIGUOUS (this charter exists to force the choice)

The goal of record (CLAUDE.md / DECISIONS 2026-05-28) is **genuinely superhuman 2p Base+Farmers play**, which
is fundamentally a **Track B** ambition (superhuman *requires* learned components to beat the heuristic). But
**all currently validated progress is Track A** (heuristic-bounded, in-ecosystem). The project is implicitly
straddling both with no declared primary.

**Recommendation:** Joshua picks one as primary for the next epoch. The honest options:
- **(P-A) Primary = Track A**, demote superhuman to aspirational. Ship/verify the strongest heuristic-bounded
  agent; treat the analyzer (Phase 5) as a near-term deliverable on top of it.
- **(P-B) Primary = Track B**, accept it is research-grade and months-to-maybe-unreachable; fund the two
  unblocks (measurement ladder, then a structural leaf/architecture change) before any more strength tuning.
- **(P-split) Both, sequenced** — Track A ships now; Track B is a gated research bet that must clear the
  measurement unblock before compute is committed.

> `TBD-Joshua` — **which track is primary** for the coming epoch (P-A / P-B / P-split).

---

## Secondary research questions (open regardless of track)

- Does the residual value-head marginal add *real* strength, or is it noise? (**CL-004** — PROTOCOL_001 running.)
- Should residual scale 0.25 go to production? (**CL-005** — *Untested*; gated entirely on CL-004.)
- Is the value head gradient-starved on the shared trunk? (**CL-008** — *Provisional*, never directly measured.)
- Can any learned component beat the v2.7 leaf standalone at matched sims? (CL-006 / CL-010.)
- The downstream prize from the original prompt: the **analyzer (Phase 5)** and **heuristic research (Phase 6)**
  — explicitly deferred behind strength milestones (DECISIONS 2026-05-28), not abandoned.

---

## Success criteria — per track

**Track A (production).** A learned-policy + v2.7 agent that beats the matched v2.7 yardstick **out-of-lineage**
(not just in-ecosystem), at margin and n `TBD-Joshua`, with a clean-ruler manifest. Aspirationally: competitive
with expert humans. Today CL-001 is only *Supported* (in-ecosystem); the out-of-lineage rung does not exist yet.
> `TBD-Joshua` — Track-A "ship" bar: out-of-lineage elo margin + n (e.g. +___ elo at n=___ paired).

**Track B (research).** A learned component that exceeds the v2.7 leaf such that strength **compounds across
iterations out-of-lineage** — a monotone climb beyond the noise band over ≥3 iterations (the falsifier on
CL-011). This is the AlphaZero/KataGo signature.
> `TBD-Joshua` — Track-B "demonstrated" bar: # iterations, per-iter out-of-lineage elo gain, noise margin.

---

## Operational definition of "superhuman" — and why it is currently UNFALSIFIABLE

"Superhuman" must be defined against a measurable referent or it cannot be claimed, won, or disproven. Proposed
skeleton (every number `TBD-Joshua`):

- **Against whom:** a strong/expert human reference, aspirationally the world champion. `TBD-Joshua` — name the
  reference opponent(s) and their accepted strength.
- **Format:** 2-player, **Base + Farmers**, no River (locked scope, DECISIONS 2026-06-02).
- **Margin:** win-rate / elo edge `TBD-Joshua` over that reference (e.g. ≥___% across ≥___ games).
- **Measured how:** a clean-ruler eval (runtime-verified provenance, 1e9 seeds, deck hashes, matched leaf;
  see `clean_eval/CLEAN_EVAL_AUDIT.md`) against the reference rung.

> **⚠️ BLOCKER — "superhuman" is currently UNFALSIFIABLE as stated.** The measuring ladder does **not yet
> exist**: there is no out-of-lineage rung and no human/expert anchor (structural blocker #1). Until the ladder
> below is built, any "superhuman" claim is unprovable *and* undisprovable. Building the ladder is the
> precondition for the goal to even be evaluable.

---

## The benchmark ladder we still need (the measurement unblock)

The single highest-leverage missing artifact. Rungs, weakest→strongest:

1. **In-ecosystem (have it):** matched-leaf HeuristicMCTS — the current clean ruler. *Same lineage / same leaf
   family* → cannot certify out-of-lineage strength.
2. **Out-of-lineage search rung (MISSING):** a strong reference outside our training lineage — e.g. high-sim
   vanilla MCTS / the Ameneyro-2020 baseline, or heur@high-sims as an absolute yardstick (CL-010's odometer).
3. **Human / expert anchor (MISSING):** the one rung that makes "superhuman" meaningful. Source `TBD-Joshua`
   (recorded expert games, a recruited strong player, or an external bot of known human-relative strength).

> `TBD-Joshua` — ladder rung definitions (which engines/opponents, at what sims) and the human-anchor source.
> Until rung 2 exists, in-ecosystem gains (CL-001/002) cannot be promoted past *Supported*.

---

## Production-agent vs research-agent criteria

| | **Production agent (Track A)** | **Research agent (Track B)** |
|---|---|---|
| Goal | strongest *verifiable* play, shippable | demonstrate genuine self-improvement |
| Leaf | v2.7 heuristic is fine (and expected) | learned component must *beat* v2.7 |
| Bar | out-of-lineage win vs matched yardstick | monotone out-of-lineage climb across iters |
| Anchor | clean ruler; human anchor aspirational | human/out-of-lineage anchor is mandatory |
| Failure | loses to v2.7 out-of-lineage | strength does not compound (CL-011 today) |

A Track-A win does **not** imply a Track-B win. Heuristic-bounded strength is allowed for production; it is
disqualifying for the research claim.

---

## Pivot conditions — Track B → Track A

Fall back to Track A as primary if, after a `TBD-Joshua`-bounded compute/time budget, **any** of:
- The measurement unblock fails — no out-of-lineage ladder can distinguish real gains from lineage overfit.
- The leaf ceiling holds — no learned component beats heur out-of-lineage (CL-010 stays *Supported*; CL-006).
- No compounding — a multi-iter run shows no monotone out-of-lineage climb beyond noise (CL-011 stays
  *Disfavored* or worsens).

> `TBD-Joshua` — the Track-B compute/time budget that triggers the pivot, and the # of failed iterations.

## Abandonment / redesign criteria

- **Redesign (not abandon):** the leaf-ceiling and flywheel-null findings *already* point at a structural
  redesign (KataGo-style domain planes + auxiliary heads + value-head-in-loop + scale, from a fresh warmstart)
  rather than more eval-config tuning. Trigger a redesign — not continued tuning — when Track B fails the
  pivot conditions but the measurement ladder is sound.
- **Abandon Track B (narrow to the analyzer):** if redesign also fails to break the leaf ceiling within a
  `TBD-Joshua` budget, narrow the *project* goal back to the original analyzer (Phase 5) win-condition. Per
  DECISIONS 2026-05-28 this is reversible and loses no analyzer work — only defers it.

> `TBD-Joshua` — the redesign budget and the abandonment trigger (what evidence ends the superhuman pursuit).

---

## Open claims (resolve in the registry, not here)

Live, unresolved claims gating these decisions — see [`governance/CLAIM_REGISTRY.csv`](governance/CLAIM_REGISTRY.csv):

- **CL-004** — residual value-head marginal real ≥2σ? *Inconclusive* — PROTOCOL_001 top-up running now.
- **CL-005** — residual scale 0.25 to production? *Untested* — gated on CL-004.
- **CL-008** — value head gradient-starved? *Provisional* — never directly measured (a Phase-B probe).
- **CL-011** — AlphaZero flywheel / compounding self-improvement? *Disfavored* — the core Track-B blocker.
- Context for the above: CL-001/002 (in-ecosystem strength, *Supported*), CL-010 (fixed-teacher ceiling),
  CL-012 (historical unmatched-leaf elos *Invalidated* — do not compare old numbers to clean-ruler numbers).

---

## Doc-conflict flag (surfaced, not papered over)

`CLAUDE.md` (top) and `docs/ORIGINAL_PROMPT.md` **directly conflict on the goal**, and the conflict is
load-bearing — not stylistic:

- **ORIGINAL_PROMPT.md** (§"Project framing", verbatim): *"This is **not** a 'build superhuman Carcassonne AI'
  project… We're not going to either,"* and *"The win condition is **(4)** [the analyzer], not raw playing
  strength."*
- **CLAUDE.md / DECISIONS 2026-05-28** reverse this: superhuman strength is **primary**; the analyzer is
  **downstream**.

CLAUDE.md flags the override explicitly, so the *intent* is clear (the 2026-05-28 change wins). The unresolved
residue is that the override points at **Track B** (superhuman ⇒ learned > heuristic), while all delivered
progress is **Track A** — and the original prompt's analyzer goal is a third, still-deferred target. This
charter does not resolve that tension; it makes it explicit and hands the primary-objective decision to Joshua
(the `TBD-Joshua` at the top).

---

*Governance spine: [`governance/README.md`](governance/README.md). Open claims:
[`governance/CLAIM_REGISTRY.csv`](governance/CLAIM_REGISTRY.csv).*
