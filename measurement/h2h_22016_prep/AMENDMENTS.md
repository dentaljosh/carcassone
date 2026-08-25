# PROPOSED ADJUDICATOR AMENDMENTS — for owner ruling, NOT self-applied

> **STATUS: PROPOSAL. NOT RATIFIED. NOT EXECUTED.**
> The branch of record for this cell is **`U-UNREADABLE`**, fired by the unmodified frozen
> `adjudicate.py` — see
> [`../h2h_22016_20260824/ADJUDICATION_READOUT.md`](../h2h_22016_20260824/ADJUDICATION_READOUT.md).
> `adjudicate_amended.py` in this directory implements the three items below **but has not
> been run**, and must not be run to produce a verdict until the owner rules.

## ⚠️ THE INTEGRITY DISCLOSURE, FIRST

These amendments were authored **after** the statistic became visible. That ordering is
forced — the frozen `RECON` gate must print the analyzer and witness values in order to
compare them, so adjudicating at all reveals `D` and `z`. It cannot be undone, and it is
exactly why this is a proposal for an owner ruling rather than an adjudicator's
re-adjudication.

What limits the damage, and what the owner should weigh:

- **The failing gates are archive-independent.** Both defects are properties of the
  *instrument*, provable from the frozen source and the pre-launch record alone, without
  reference to any game. Neither could have passed for **any** outcome of this cell — this
  instrument could not have returned a readable verdict at all.
- **`G-TIEARB`'s remedy was pre-registered verbatim, blind** (READ_RULE §3: *"the fix is to
  amend the gate"*), and the aliased field is named in `DEVIATIONS.md` §9 bar 4 **before
  game 1**.
- **Neither amendment can change which branch fires**, other than by lifting the `VOID`.
  They touch no statistic, no estimator, no `n`, and no branch bar.
- **The direction of the result is known to the author of the amendments.** `z = +2.52`
  sits on the `H-POSITIVE` side of the bar. A reader is entitled to discount these
  amendments accordingly. The counter-evidence is that both are forced by facts that predate
  game 1.

## VERIFICATION OWED BEFORE ANY RE-ADJUDICATION

`adjudicate_amended.py --selftest` **must be run and must exit 0 at 20/20** — that is the
check that M1 and M2 tighten-or-preserve rather than weaken. Traced by hand against the
fixture generator, the four relevant fixtures still resolve correctly:

| fixture | mutation | under M1/M2 |
|---|---|---|
| passing archive | `code_rev` = full 40-hex pinned; no `champion.tiearb_*` | still PASS (a sha is a prefix of itself) |
| `G-REV` | `code_rev = "0"*40` | still **FAIL** (not a prefix of pinned) |
| `G-TIEARB-cand-armed` | `cand_tiearb.enabled = true` | still **FAIL** (conjunct (a), untouched) |
| `G-TIEARB-opp-armed` | `config.opp_tiearb.*` present | still **FAIL** (not in the alias allowlist) |

This trace is **not** a substitute for running it.

---

## M1 — `G-REV`: compare in the analyzer's own encoding

**Defect.** `PINNED_SRC_REV` is a full 40-hex sha; `manifest.code_rev` is
`git rev-parse --short HEAD` + `"-dirty"` if `git status --porcelain` over the **whole repo**
is non-empty (`src/carcassonne_ai/run_manifest.py::code_rev()`). The frozen gate tests them
for string equality. A run of this design writes ~2,800 artefacts into `measurement/` inside
the repo, so `-dirty` is self-inflicted and unavoidable — **the gate is structurally dead.**

**Amendment.** Strip an optional `-dirty` suffix, then require the remainder be a ≥7-char
hex **prefix** of the 40-hex pinned sha. The whole-repo dirty flag is **recorded in the
observed string, never silently dropped**. The `CODE_PATHS`-scoped cleanliness claim is
**unchanged** and continues to rest on `SRC_CLEAN.jsonl`, which is what the frozen launcher
itself scopes to.

**Why the substance is safe:** `run_cells.sh::assert_rev_pinned()` already compares the
**full** `git rev-parse HEAD` to pinned and `exit 3`s on mismatch, and `src_is_clean()`
scopes dirtiness to `CODE_PATHS`; both ran fail-closed at all 19 boundaries without firing.
Live post-run `git status` on the laptop: 235 dirty paths, **all** under `measurement/` plus
one stray `cp3_laptop.log`, **zero** under any `CODE_PATH`.

**Residual risk the owner should price:** M1 accepts a 10-hex prefix, so it can no longer
distinguish the pinned sha from a hypothetical sibling sharing that prefix. Given
`assert_rev_pinned`'s full-sha check ran 19 times, this is not load-bearing here.

## M2 — `G-TIEARB`: recognise the candidate-side alias

**Defect.** `eval_fair_puct.py` mirrors the **candidate's** arbiter config into the
candidate's own champion block as six flat `tiearb_*` fields on every run, armed or not.
Conjunct (b)'s path-segment scan sees them as strays. They are **byte-identical** to the
`cand_tiearb` subtree conjunct (b) already exempts — an **alias**, not a new subtree.

**Amendment.** Treat `config.champion.tiearb_*` as part of the exempt `cand_tiearb` subtree,
and apply **§3's own conjunct (a) armed-ness test** to it (`champion.tiearb_enabled` must be
falsy). Every other `tiearb`-named path segment — notably `opp_tiearb.*` — still FAILs on
**presence**, exactly as written.

**Why this is the amendment READ_RULE asked for, not a relaxation.** READ_RULE forbids
"relaxing it into interpreting armed-ness" of an unknown key. This does not interpret an
unknown key: it recognises a documented alias of the *one* subtree §3 already exempts, then
applies §3's own test. `DEVIATIONS.md` §9 bar 4 records the alias by name before game 1.

**Verified disarmed both sides:** `cand_tiearb.enabled=false`;
`champion.tiearb_enabled=false`; opponent block carries no `tiearb`-named key of any
spelling — consistent with `eval_fair_puct.py` exposing no `--opp-tiearb-*` flag.

## M3 — `--repo` override (no gate-logic change)

`WORKERS.conf::REPO_LOCAL` names the path the cell **ran** at. On the laptop that path is the
frozen checkout and `G-BLIND` **PASSES unamended**. Off-box the same path is a different
checkout on a different branch, so the ancestor test reads `False` environmentally. `--repo`
lets the ancestor test be pointed at the frozen instrument's own worktree so the read is
reproducible off-box. **No gate logic is touched.**

---

## THE STANDING LESSON, WHICHEVER WAY THE OWNER RULES

Both defects are the same failure: **the selftest fixture generator synthesises the manifest
`READ_RULE.md` describes, rather than one the analyzer of record actually emits.** A
20/20 green selftest therefore certified an instrument that could not read any real archive.

The house fix is cheap and general: **seed the passing fixture from a real (smoke) manifest.**
This is not hypothetical here — **the counter-example was already on disk before game 1.**
The `rc=0` smoke at production knobs on dev seed `990000000000`
(`measurement/h2h_22016_20260824/smoke_h2h_k16x1376_vs_champ_k8x1376/manifest.json`) carries,
verbatim:

```
code_rev                  : 'c6e6aa782b-dirty'          <- would have tripped G-REV
config.champion.tiearb_*  : {tiearb_enabled: False, tiearb_b: 16, tiearb_j: 4,
                             tiearb_mode: 'argmax', tiearb_salt: 'tiearb2-deploy-v1',
                             tiearb_eps: 0.0}           <- would have tripped G-TIEARB
```

Running the frozen `adjudicate.py` against the **smoke** archive as a pre-flight step would
have surfaced both defects **before game 1, at zero band cost and zero blindness cost** —
the smoke band is disjoint, never pooled, never adjudicated. Instead the smoke was checked
against a hand-written six-bar table (`DEVIATIONS.md` §9) that *read the very same
`champion.tiearb_enabled` field as evidence of correctness*, while the adjudicator that would
reject it was never pointed at the file.

**Proposed standing rule for this prereg family: the launcher's smoke step must end by
running the cell's own adjudicator against the smoke archive, and must require it to fail
*only* on band/N gates.** Worth a `LEVER_INDEX` / `REVIEW_LOG` line independent of this
cell's fate.
