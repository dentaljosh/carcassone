# PROJECT CHARTER — Carcassonne AI

> # ⚠️ SUPERSEDED / STALE — DO NOT ADOPT THIS DOC'S PRIMARY TRACK OR ITS NUMBERS
>
> **Stamped 2026-07-30 (buried-caveats audit F6). Last substantive edit `7c5ca3d`, 2026-06-08 — 52 days
> before this banner, and two evidence epochs plus one champion ago.** It is kept as the 2026-06-08
> decision record; it is **not** current state. A fresh thread that follows
> [`governance/README.md`](governance/README.md) into this file today adopts the wrong primary track and
> a stale champion.
>
> **CURRENT AUTHORITY:** [`CLAUDE.md`](CLAUDE.md) (goal + the two structural blockers) ·
> [`docs/PROGRAM_ROADMAP_2026-07-07.md`](docs/PROGRAM_ROADMAP_2026-07-07.md) (**the live work queue**) ·
> [`STATUS.md`](STATUS.md) (state snapshot) · [`governance/PRODUCTION.yaml`](governance/PRODUCTION.yaml)
> (the champion of record) · [`experiments/results.csv`](experiments/results.csv) (numbers).
>
> **Three specific contradictions, so nobody has to diff it:**
> 1. **Primary track.** This doc says *"Track B (genuine self-improvement) is primary; superhuman vs
>    humans is DEFERRED/aspirational"*. `CLAUDE.md` has said the **opposite since 2026-05-28** —
>    superhuman is the **primary** goal and the analyzer/Phase 6 are downstream. CLAUDE.md governs.
> 2. **The leaf-ceiling citation.** This doc asserts *"CL-010 stays **Supported**"*. CL-010 was
>    **`Provisional` from 2026-06-08** and is **`SUPERSEDED` as of 2026-07-30**: its falsifier ran
>    2026-06-19 and went un-adjudicated for 41 days. **The blocker's conclusion still holds** — it now
>    rests on CL-039/CL-042/CL-064/CL-065/CL-066 + CL-073, not on CL-010. See CLAUDE.md blocker #2.
> 3. **Champion / numbers.** The `iter_11 +89.7` and residual `+83.2` quoted below as *"where the current
>    validated gains live"* are **neural-era and two epochs dead**. The champion has been **classical**
>    since 2026-07-07 and its budget was promoted to k8×1376 on 2026-07-29 (CL-071).
>
> *Original 2026-06-08 banner follows.*

> **Primary track DECIDED 2026-06-08 (Joshua): P-B — Track B (genuine self-improvement) is primary;
> "superhuman vs humans" is DEFERRED/aspirational** (no measurement path exists yet, so it is not a
> near-term success criterion). Numeric go/no-go thresholds below were **RATIFIED by Joshua on 2026-06-08**
> (they now bind; revisit if one proves wrong in practice).
> This charter sits in the **DECISIONS** layer of the governance spine (see `governance/README.md`). It
> points to live context rather than restating it: [`CLAUDE.md`](CLAUDE.md) (goal change + two structural
> blockers), [`docs/ORIGINAL_PROMPT.md`](docs/ORIGINAL_PROMPT.md) (the original analyzer win-condition this
> goal overrides), [`DECISIONS.md`](DECISIONS.md) 2026-05-28 "Goal change" + 2026-06-08 "Track decision".
> Claim ids resolve in [`governance/CLAIM_REGISTRY.csv`](governance/CLAIM_REGISTRY.csv).

---

## The two tracks (do NOT silently merge them)

This project contains two distinct efforts that are easy to conflate. The charter's first job is to keep
them apart; its second (now done) was to declare which is primary.

**Track A — Strong verifiable agent (production-oriented).**
Strongest learned **policy** wrapped around the hand-crafted **v2.7 `virtual_score`** search leaf. The agent
is PUCT search over a human-designed heuristic; the net contributes priors (and, candidate, a residual value
head). This is **where the current validated gains live**: iter_11 **+89.7** elo and the residual net **+83.2**
elo, both *in-ecosystem* vs our own matched-leaf HeuristicMCTS yardstick (CL-001, CL-002). Production-oriented:
ship the strongest thing we can *verify*, even if its strength is heuristic-bounded.

**Track B — Genuine self-improvement (research-oriented). ← PRIMARY (2026-06-08).**
A **learned value** that participates in AND improves the search teacher — an AlphaZero/KataGo-style climbing
curve where strength compounds across iterations because the learned component *exceeds* the heuristic leaf.
**Current status: NOT demonstrated.** Blocked by the two structural walls from `CLAUDE.md`:
1. **Measurement** — no strong, non-saturated, *human-anchored* reference exists (Tier-1 saturated; self-anchored
   elo can climb while absolute strength regresses). **Partial relief:** an *out-of-lineage* gauge now exists (the
   asymmetric ladder `scripts/ladder_asymmetric.py`, heur@{200,800,3200}); the *human* anchor does not (deferred).
2. **Leaf ceiling** — the v2.7 leaf caps learned strength near strong-human *by construction* (CL-010); the
   learned components do not yet exceed it.
   Plus: the Lever-3 residual flywheel was **NULL for compounding** (CL-011 *Disfavored*) — iter0 best, iter1
   regressed, iter2 tied within noise. **Flipping CL-011 is the primary objective's falsifier (see below).**

Track A can succeed (ship a strong heuristic-bounded agent) while Track B remains entirely undemonstrated.
They are not the same project and must not be reported as one.

---

## Primary objective — DECIDED: P-B (Track B primary), superhuman DEFERRED

**Decision (Joshua, 2026-06-08):** Track B — genuine self-improvement — is the **primary objective**.
The ultimate "beat strong/expert humans, aspirationally the world champion" goal is **kept but DEFERRED**:
it is currently **unmeasurable** (no human/out-of-lineage-strength anchor), so it is the *aspirational north
star*, **not** a near-term success bar.

**Operational consequence — the near-term Track-B objective is MEASURABLE today:** demonstrate a genuine
**out-of-lineage climbing curve** — strength that compounds across self-improvement iterations on the
asymmetric ladder (the gauge we already have). In one line: **flip CL-011 from *Disfavored* to *Supported***.
Superhuman-vs-humans is promoted from aspiration to active goal *only after* the human-anchor rung (below) is
built. Until then we do not claim, target, or measure "superhuman."

This means the project explicitly accepts (per Joshua) that Track B is **research-grade and
months-to-maybe-unreachable** with 3 GPUs ≪ known superhuman recipes; the two unblocks (sound out-of-lineage
measurement → then a structural leaf/architecture change) come **before** any more eval-config strength tuning.

---

## Secondary research questions (open regardless of track)

- Does the residual value-head marginal add *real* strength, or is it noise? (**CL-004** — PROTOCOL_001 running.)
- Should residual scale 0.25 go to production? (**CL-005** — *Untested*; gated entirely on CL-004.)
- Is the value head gradient-starved on the shared trunk? (**CL-008** — *Provisional*, never directly measured;
  a Phase-B observability probe. Directly relevant to Track B: it's a candidate *mechanism* for the flywheel null.)
- Can any learned component beat the v2.7 leaf standalone at matched sims? (CL-006 / CL-010.)
- The downstream prize from the original prompt: the **analyzer (Phase 5)** and **heuristic research (Phase 6)**
  — deferred behind strength milestones (DECISIONS 2026-05-28), not abandoned; the Track-B abandonment path
  (below) narrows back to exactly this.

---

## Success criteria — per track

**Track B (PRIMARY, research).** A learned component that exceeds the v2.7 leaf such that strength **compounds
across iterations out-of-lineage** — a non-regressing climb beyond the noise band (the falsifier on CL-011).
> **RATIFIED (Joshua, 2026-06-08)** — Track-B "demonstrated" bar:
> **≥3 consecutive self-improvement iterations**, each adding **≥ +15 elo out-of-lineage** vs a FIXED reference
> rung (heur@800; see ladder), **cumulative ≥ +45 elo** over the iter-0 baseline, with **no single-iteration
> regression beyond the gate noise** (gate at **n ≥ 400 paired** → ±17 elo, so "no regression" = no iter drops
> > ~20 elo). Rationale: this clears the odometer's ~1-doubling-of-depth, exceeds the ±21 gate noise that hid
> the flywheel null, and rules out the iter1 −50 / iter2-tied pattern we actually saw. Measured on the clean ruler.

**Track A (fallback/production).** A learned-policy + v2.7 agent that beats a matched yardstick **out-of-lineage**
(not just in-ecosystem). Today CL-001 is only *Supported* (in-ecosystem); the out-of-lineage win does not exist
(the net loses to heur@800 by −29, heur@3200 by −38 on the odometer).
> **RATIFIED (Joshua, 2026-06-08)** — Track-A "ship" bar: **beats heur@800 out-of-lineage by ≥ +30 elo at
> n = 400 paired** (≈2σ; heur@800 is 4× our search depth, never-gated, out-of-lineage). Tighten to n=600–800 if
> a ship decision is imminent. **Currently UNMET.**

---

## Operational definition of "superhuman" — DEFERRED (kept aspirational)

> **DECISION (Joshua, 2026-06-08): DEFER.** "Superhuman" is kept as the aspirational north star but is **NOT a
> near-term success criterion** and **NOT currently measured**, because no human/out-of-lineage-strength anchor
> exists (structural blocker #1). Setting a binding referent/margin is **deferred until the human-anchor rung
> (below) is built.** Until then any "superhuman" claim is unprovable *and* undisprovable — so we don't make one.

Skeleton to be completed *when* the anchor exists (do NOT fill until then):
- **Against whom:** a strong/expert human reference, aspirationally the world champion. *DEFERRED — name when rung 3 exists.*
- **Format:** 2-player, **Base + Farmers**, no River (locked scope, DECISIONS 2026-06-02). *(this one is fixed)*
- **Margin:** win-rate / elo edge over that reference. *DEFERRED.*
- **Measured how:** clean-ruler eval (runtime-verified provenance, 1e9 seeds, deck hashes, matched leaf) vs the anchor rung.

---

## The benchmark ladder (the measurement unblock)

The single highest-leverage area. Rungs, weakest→strongest:

1. **In-ecosystem (HAVE):** matched-leaf HeuristicMCTS@200 — the current clean ruler. Same lineage / same leaf
   family → cannot certify out-of-lineage strength. (CL-001/002 are pinned here → capped at *Supported*.)
2. **Out-of-lineage search rung (HAVE, as of 2026-06-07):** the asymmetric ladder `scripts/ladder_asymmetric.py`
   — heur@{200, 800, 3200} as absolute yardsticks (CL-010's odometer). **PROPOSED:** the **fixed Track-B gating
   reference = heur@800** (4× our depth, never-gated, out-of-lineage). This is the rung the climbing-curve bar
   above is measured against.
3. **Human / expert anchor (MISSING — DEFERRED):** the rung that makes "superhuman" meaningful. **DEFERRED per
   Joshua (2026-06-08)** — keep aspirational; do not source a referent until Track B clears its out-of-lineage
   bar. Candidates when revisited: recorded expert games, a recruited strong player, or an external bot of known
   human-relative strength.

> **RATIFIED (Joshua, 2026-06-08)** — gating reference = heur@800 out-of-lineage at n≥400 paired (rung 2).
> Rung 3 (human anchor) intentionally deferred. Out-of-lineage rung 2 EXISTS, so Track-B progress IS measurable
> now even with superhuman deferred — this is what makes the P-B decision actionable rather than blocked.

---

## Production-agent vs research-agent criteria

| | **Production agent (Track A)** | **Research agent (Track B) ← primary** |
|---|---|---|
| Goal | strongest *verifiable* play, shippable | demonstrate genuine self-improvement |
| Leaf | v2.7 heuristic is fine (and expected) | learned component must *beat* v2.7 |
| Bar | out-of-lineage win vs matched yardstick (+30 @ heur@800, proposed) | non-regressing out-of-lineage climb across ≥3 iters (proposed) |
| Anchor | clean ruler; human anchor aspirational | out-of-lineage rung 2 mandatory; human anchor deferred |
| Failure | loses to v2.7 out-of-lineage (today) | strength does not compound (CL-011 *Disfavored* today) |

A Track-A win does **not** imply a Track-B win. Heuristic-bounded strength is allowed for production; it is
disqualifying for the (primary) research claim.

---

## Pivot conditions — Track B → Track A

Fall back to Track A as primary if, within the budget below, **any** of:
- **Measurement fails** — the out-of-lineage ladder cannot distinguish real gains from lineage overfit.
- **Leaf ceiling holds** — no learned component beats heur@800 out-of-lineage (CL-010 stays *Supported*; CL-006).
- **No compounding** — a multi-iter run shows no non-regressing out-of-lineage climb beyond noise (CL-011 stays
  *Disfavored* or worsens).

> **RATIFIED (Joshua, 2026-06-08)** — Track-B budget before pivot: **≤2 funded structural attempts** (e.g. a
> retuned in-loop flywheel, then a higher-capacity-leaf redesign), **each ≤ ~7 days wall-clock on the 3-box
> cluster**; if neither clears the Track-B "demonstrated" bar, pivot to Track A primary. (Compute reality: 3 GPUs,
> a flywheel iteration is ~hours-to-a-day of gen+train+gate — 7 days allows ~3–5 iters per attempt, enough to
> see a curve or its absence.)
>
> **UPDATED (Joshua, 2026-06-08 pm) — budget RELAXED, ≤2-attempt cap LIFTED.** After attempt #1 (`flywheel_residual_v2`)
> came back CL-011-null but *informative* (it surfaced the keep-best-on-in-lineage-gate mis-selection + the
> S-R3-1 tanh-cap), Joshua is **fine with ~10 more iters of flywheel/research iteration** (multiple attempts OK).
> The pivot-to-Track-A clock is **PAUSED** — keep iterating on Track B. Pivot/abandon remains the eventual
> fallback but is no longer bounded to 2 funded attempts.

## Abandonment / redesign criteria

- **Redesign (not abandon):** the leaf-ceiling + flywheel-null findings already point at a *structural* redesign
  (KataGo-style domain planes + auxiliary heads + value-head-in-loop + scale, from a fresh warmstart) rather than
  more eval-config tuning. Trigger a redesign — not continued tuning — when the *first* funded attempt fails the
  Track-B bar but the measurement ladder is sound.
- **Abandon Track B (narrow to the analyzer):** if the redesign attempt also fails to break the leaf ceiling
  within its budget, narrow the *project* goal back to the original analyzer (Phase 5) win-condition.
> **RATIFIED (Joshua, 2026-06-08)** — redesign budget: **1 structural-redesign attempt, ≤ ~10 days wall-clock**,
> only after cheap levers are exhausted. **Abandonment trigger:** that redesign completes its budget with CL-010
> still *Supported* AND CL-011 still *Disfavored* (no learned component beats heur@800 out-of-lineage, no
> compounding) → end the superhuman pursuit, resume the analyzer. Per DECISIONS 2026-05-28 this is reversible and
> loses no analyzer work — only defers it.

---

## Open claims (resolve in the registry, not here)

Live, unresolved claims gating these decisions — see [`governance/CLAIM_REGISTRY.csv`](governance/CLAIM_REGISTRY.csv):

- **CL-011** — AlphaZero flywheel / compounding self-improvement? *Disfavored* — **THE primary objective's
  falsifier.** The whole P-B bet is: can we flip this to *Supported* on the out-of-lineage ladder?
- **CL-004** — residual value-head marginal real ≥2σ? *Inconclusive* — PROTOCOL_001 top-up running now.
- **CL-005** — residual scale 0.25 to production? *Untested* — gated on CL-004 (a Track-A production question).
- **CL-008** — value head gradient-starved? *Provisional* — never directly measured; a candidate *mechanism* for
  the CL-011 null, so a Phase-B observability probe is on the Track-B critical path.
- Context: CL-001/002 (in-ecosystem strength, *Supported*), CL-010 (fixed-teacher ceiling, *Supported*),
  CL-012 (historical unmatched-leaf elos *Invalidated* — never compare old numbers to clean-ruler numbers).

---

## Doc-conflict flag (surfaced; now partly resolved by the P-B decision)

`CLAUDE.md` (top) and `docs/ORIGINAL_PROMPT.md` conflict on the goal, load-bearingly:

- **ORIGINAL_PROMPT.md** (§"Project framing", verbatim): *"This is **not** a 'build superhuman Carcassonne AI'
  project… We're not going to either,"* and *"The win condition is **(4)** [the analyzer], not raw playing strength."*
- **CLAUDE.md / DECISIONS 2026-05-28** reverse this: superhuman strength is **primary**; the analyzer is **downstream**.

**Resolution status:** the 2026-05-28 override wins, and the 2026-06-08 P-B decision affirms Track B (the
superhuman direction) as primary — **with the honest caveat that all *delivered* progress is Track A** and the
superhuman *measurement* is deferred. The original prompt's analyzer goal is the explicit **abandonment landing
zone** (above), not a competing live target. The residual tension (primary bet = the currently-*Disfavored*
CL-011) is real and is precisely what the pivot/abandonment budgets bound.

---

*Governance spine: [`governance/README.md`](governance/README.md). Open claims:
[`governance/CLAIM_REGISTRY.csv`](governance/CLAIM_REGISTRY.csv). Strategic thresholds above were
RATIFIED by Joshua on 2026-06-08 (they bind; revisit if one proves wrong).*
