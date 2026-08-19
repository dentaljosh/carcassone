# REVIEW — the `B = 64` game-cell pair (draft `0c373671`)

**VERDICT: FAIL — 1 BLOCKING, 4 REQUIRED, 2 COSMETIC. The six §10 choices are RULED below.**

The blocking item is a gate that **fails on every healthy run** — the disease class this campaign
has killed five times. Everything else is strong: **every arithmetic chain I re-derived from
primitives reproduces exactly**, the existence-time markers are applied correctly, and the
disclosed `√2` contradiction is diagnosed right.

## What I re-derived from primitives, and it all checks

| chain | verdict |
|---|---|
| `sd = 0.6906057781774855 × √400 = 13.812` | ✅ source values read off `tiearb2_stage2_20260817/READOUT.json` — exact |
| `se_cell(750) = 13.812/√750 = 0.50435`; `se(D) = √2 × = 0.71326`; `2σ = 1.4265` | ✅ matches 0.5044 / 0.7133 / +1.427 |
| bracket `0.0670 × 17.5725 / 3.2 = 0.36793`; `× 3.9 = 1.4349` | ✅ matches [+0.368, +1.435] |
| cost chain: 52.4862 → 3.2804 → 0.191225 → 10.0381 → 40.1524 → base 253.218 → NARROW 429.612 (identity ✓) → WIDE 958.794 (= 2.232×) | ✅ every step |
| bill 644,418 + 1,438,191 = 2,082,609 s = 578.5 wh; /52 = 11.13 h; ×1.19 = **13.24 h** | ✅ |
| derate `4.41 / ((343,689.685+350,061.865)/52/3600) = 4.41/3.706 = 1.190` | ✅ measured, not assumed |
| `G-N`: 1,200 games ≡ 600 decks against 1,500/750 — reachable and binding | ✅ Stage 2's unreachable version correctly fixed |

**The `√2` contradiction (§6.4): CONFIRMED.** `1.4/0.6906 = 2.027` — PLAN_B graded against the
**single-cell** `se`. With `se(D) = √2·se_cell = 0.9766`, `1.435/0.9766 = 1.469` — it does not
convict. The companion "n ≈ 12,500 for +0.35" is likewise single-cell (11,272 games); the correct
figure is **11,270 decks = 22,540 games**. ⇒ **`PLAN_B_gt_16.md` §5 needs an erratum line**; both
figures are superseded by §6.2/§6.3.

**The nested-CRN finding (§1.3): CONFIRMED AT THE SOURCE.** `tiearb.rs::arbitrate` computes
`world_seed = seed_i64(&[salt, digest, ply, j])` inside `for j in 0..b` — **`b` never enters the
derivation**, so worlds `0..15` at `B=64` are byte-identical to `B=16`'s. Structural, not
incidental, and it is the same prefix-stability property `oracle_score_pilot` has. `G-NEST` is
well-posed: it pins the witness at HEAD and can fail if the code moves.

---

## BLOCKING

**B1 — `G-TOOL` fails on EVERY healthy run.** The row reads: *"A `+rustcunpinned` or otherwise
sentinel value is **unknown provenance, which is not agreement** ⇒ fail."* But
`rust_agent.py:372` is `tc = os.environ.get("RUSTUP_TOOLCHAIN") or "unpinned"` — **`unpinned` is
the normal value whenever the toolchain is not pinned, which is the production condition.**
`DEVIATIONS.md` §D4.13 records both boxes emitting exactly
`carc_rs-0.1.0+<rev>+rustcunpinned` on the R4 run. **As written this gate returns
`U-UNREADABLE` on every run this programme can currently produce** — the `G-CAP` / R1-four /
R4-0.2 class, and the one thing §3's own scope-marker discipline exists to prevent.

**FIX:** `G-TOOL`'s conjunct is **equality of `carc_rs_build` across boxes**, which is what the JCZ
ruling actually says. `unpinned` is a legitimate value **provided it is equal on both boxes** —
equality is the property that matters, not pinning. If pinned toolchains are wanted, that is a
change to the launch environment, not a gate that voids everything. Keep the rest of the row (the
`carc_rs_binary_sha` never-across-boxes rule, the `PREFLIGHT_*_FIRST.json` authority under
`--shared-claim`) unchanged — those are correct.

---

## REQUIRED

**R1 — State the REACHABLE BRANCH SET under each value of `A`, at the top of §4.** §4 correctly
says the first disjunct of `A` is FALSE by committed arithmetic, but it never states the
consequence as a set. **Absent `OWNER_WAIVER.md`, the reachable branches are
`{B-REVERSED, B-COSTKILL, B-PRESENT, B-FLAT, U-UNREADABLE}` and `B-CONFIRMED` is UNREACHABLE.**
That is exactly the Stage-2 `G-N` lesson the draft itself cites — an unreachable headline branch
must be visible *before* the run, not discovered in the read-out. **Do not assume the waiver**
(ruling 2 below).

**R2 — `G-DIVERGE`'s floor: keep 0.10, but print the EXPECTED value beside it.** Sanity-checked as
asked: the offline pick-churn per doubling is ~0.29 per fired ply (0.303/0.309/0.290/0.287), and a
deck carries ~35 fired plies (`phi` 17.5725 × 2 seats), so the expected per-deck divergence is
`1 − 0.71^35 ≈ 1.0`. **The floor therefore carries ~10× headroom: it is an INERTNESS detector, not
a power check, and that is the right role for it.** But a realized `1−f₀` of, say, 0.15 would
*pass* while being wildly below expectation — an anomaly that must not read as a pass. **Print the
expected ≈1.0 beside the realized in the §4.3 divergence block**, so a barely-passing value is
legible.

**R3 — `PLAN_B_gt_16.md` §5 erratum line** for the two superseded power figures (above).

**R4 — The `A` waiver file must be checked for CONTENT, not only existence and timestamp.** §4
says the file must *"carry a dated VERBATIM owner quote waiving the N4 `rho_wall` bar for
`B > 16`"* — good — but the mechanical check described is existence + timestamp. **Specify what
makes the content check mechanical** (e.g. the file must contain a line matching a committed
pattern naming `rho_wall` and the rung), or the gate is a human judgement wearing a file check's
clothes.

---

## COSMETIC

**C1 — `f₀`'s direction is right and the disclosure is right**, but say it in one more word:
`D_i = 0` **overcounts** identity (two different games can coincide on margin), so `1−f₀`
**undercounts** divergence ⇒ the floor is **conservative**. The draft says "upper bound on true
game-identity", which is correct but leaves the reader to work out the direction of conservatism.

**C2 — §7.2's `A_bar` +9.3% and `c_incell` +7.3% deltas** are correctly flagged as reported and
not load-bearing. Worth one clause saying *why* they cannot bite: the chain uses **measured
seconds**, never `A_bar`, so the deltas cannot propagate.

---

## RULINGS on the six §10 choices

**1 — CONTRAST SHAPE: keep the two differenced cells. CONFIRMED.** The head-to-head is probably
cheaper and stronger, but it buys that with (i) an **unmeasured dispersion** — sizing `n` from the
smoke is sizing on data, which §6.5 forbids for exactly this reason — and (ii) a new
**opponent-side** instrument where a bug is invisible to `G-J1`-class candidate gates. The
programme's two most expensive recent losses (R3.3, S2) were **design-shape** failures, not power
failures. Take the known shape.

**2 — N4 WAIVER: do NOT ask, do NOT assume. Say it in the branch table. CONFIRMED as drafted,
plus R1.** The owner is away; a waiver cannot be obtained before the run; and moving a cost bar the
owner set is outside a drafting delegation. The honest posture is the drafted one — `A` is decided
by a pre-dated file, and absent it the ceiling is `B-COSTKILL`. R1 makes that ceiling explicit.

**3 — `n` = 1,500: ACCEPTED.** It is the smallest rung that can convict the top of the §5.2
bracket (`floor 1.427` vs `bracket top 1.435`, `z ≈ 2.01`); 1,200 cannot (floor +1.595). 13.2 h
fits the 20 h delegation with margin for the smoke and preflights.

**4 — `B = 32`: KEEP `B64`-vs-`16` AS DRAFTED. Three cells DECLINED.** ⭐ **The EV argument turns
on a fact that dissolves the apparent advantage: `rho_wall(32)` = 1.2449 > 1.20, so `A` is FALSE
for `B = 32` TOO.** A `B=32` win is *also* `B-COSTKILL` absent a waiver — swapping the primary buys
**no deploy licence**. Given that neither rung can deploy, the run's value is scientific, and there
`B = 64` **dominates**: the largest offline Δ (+0.0670 vs +0.0597), 48 extra worlds vs 16, hence
the best chance of detecting *any* game-level effect — and, decisively, **a `B-FLAT` at `B = 64`
bounds the whole axis** (if the biggest rung does not express at `n` = 1,500, the smaller one will
not either), whereas a flat at `B = 32` leaves `B = 64` open. That is the higher **kill quality**,
which this programme explicitly optimises for. `B = 32`'s advantage is contingent on a win *and*
then still needs a waiver or a 3.7% cost shave.
⚠️ **I decline to compare the two rungs' POWER**, because doing so requires multiplying by the
offline→game map that §5.2 forbids using as a multiplier. The comparison above rests only on
committed constants and on kill quality — not on a projection.
**On three cells:** the draft's multiplicity argument is **weaker than it states** — one
pre-registered primary plus non-adjudicating riders is this programme's standard pattern and would
handle multiplicity cleanly. I decline it on **schedule risk**, not statistics: three cells cost
≈831 wh ≈ **19.0 h** of two-box wall against a 20 h delegation, leaving no margin for the smoke,
the preflights, or any re-run. **The drafted design already sequences the ladder correctly** —
`B-COSTKILL` clause (ii) names the `B=32` question as licensed-but-unfunded, so you pay for `B=32`
only if `B=64` shows something.

**5 — `G-DIVERGE` 0.10: KEEP, with R2's expected-value print.** Sanity-checked above: expected
`1−f₀ ≈ 1.0`, so 0.10 is a ~10× headroom inertness floor. Correct role, loose by design, and the
looseness is safe *because* a tighter floor risks failing a healthy run — but only once the
expected value is printed beside it.

**6 — `N_SMOKE` = 24 and band `900000300000`: ACCEPTED**, mechanical. One condition: the throwaway
band must be **declared throwaway in the smoke manifest** — never claimed in `BAND_REGISTRY.csv`,
never read for an outcome — so it cannot later be mistaken for a claimed band.

---

## Disposition

**FAIL.** Fix **B1** (which is one sentence of conjunct text and would otherwise void the run),
fold **R1–R4**, and the pair is ready for blind commit with the six rulings above recorded in it.
C1–C2 at the drafter's discretion. **No re-review needed for R1–R4 or the cosmetics; B1 should be
re-read by whoever merges**, since it is the one change that alters a gate's conjunct.
