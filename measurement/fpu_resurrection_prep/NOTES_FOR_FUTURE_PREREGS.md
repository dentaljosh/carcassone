# Notes for future preregs — instrument-authoring guidance

This round's frozen adjudicator gates (`G-N`, `G-DECKS` in `run_cells.sh`/`screen_lib.py`)
were implemented **stricter** than the DESIGN/READ_RULE prose actually said. The prose
tolerated a sub-2% failure rate ("a failure rate strictly below 2% is REPORTED, never
silently absorbed... at or above it the cell voids") and an `n_common >= 80% of 400`
common-deck bar, but the coded conditions demanded exact equality (`n == 800`,
`n_failed == 0`, `n_common == 400`) — stricter than the frozen prose that was supposed to
govern them. This was adjudicated as an amendment (frozen-arithmetic, no judgment) rather
than a retro-edit of the frozen round: **[AMENDMENTS.md](AMENDMENTS.md) FPU-A1**.

⛔ **This round's frozen files (DESIGN.md, READ_RULE.md, gate code) do NOT move** — a
frozen round stays frozen; the correction lives only in this note and in FPU-A1, for the
NEXT round's author.

## The guidance itself

**State gate strictness EXACTLY — a tolerance in prose is not automatically the tolerance
the code enforces.** If a gate's design or READ_RULE prose says "a failure rate strictly
below X% is tolerated," the coded condition must implement that exact tolerance (e.g.
`n_failed <= floor(n * X/100)`), not a stricter proxy (`n_failed == 0`) that happens to
usually agree. When prose and code diverge, the reasoned prose is the law of the pair — but
divergence discovered mid-round forces a statistics-blind amendment instead of a clean
read, and (per FPU-A1's read-rule) can leave the branch UNRESOLVED where a correctly-coded
gate might have resolved cleanly.

**Checklist before freezing a gate:**
- For every numeric bar in DESIGN.md/READ_RULE.md prose ("below 2%", "at least 80% of
  400"), grep the adjudicator code for the literal condition that enforces it, and confirm
  the two match arithmetically — not "usually agree," match.
  the b32v64 0.100% rust-panic precedent is the worked example this round's prose cited;
  reuse its documented tolerance rather than re-deriving one.
- If the gate is meant to be exact-equality (no tolerance), say so explicitly in the prose
  too, so a reader can't reasonably infer a tolerance that was never coded.
- Selftest fixtures should include a case at the tolerance BOUNDARY (e.g. exactly 2%
  failure, or exactly 320/400 common decks) so a strictness mismatch fails in `--selftest`
  before any real cell spends compute — not after, statistics-visible, requiring an
  amendment like this one.
