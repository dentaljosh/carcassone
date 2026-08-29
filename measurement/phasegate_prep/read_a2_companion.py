#!/usr/bin/env python3
"""A2 companion reader — FROZEN BLIND 2026-08-29 ~04:3xZ, before any EXT record
was read (the orchestrator peeked at exactly one already-adjudicated A1
ARB_FULL record to learn the schema; zero EXT_* files were opened).

WHAT THIS IS: the pre-registered POOLING RULE and the widened deck-paired
FULL−EARLY companion contrast for the A2 extension (executor handoff item 1:
"A2 owes its own reader"). It is a COMPANION READING — DESIGN §3.2/§4.4 forbid
it as a branch input; it fires no branch, changes no A1 verdict, and its
numbers travel with that label.

POOLING RULE (stated before data): gate=all decks = ARB_FULL (seeds
154000000000..399, the frozen anchor) ∪ ARB_FULL_EXT_L (..400..829) ∪
ARB_FULL_EXT_R (..830..1199) — 1,200 decks, disjoint by construction (the
launcher guard); gate=early decks = ARB_EARLY_L ∪ ARB_EARLY_R (same 1,200 seed
range, already adjudicated). Readings:
  (1) widened anchor margin M_all over 1,200 paired decks (champion+arb(all)
      minus champion), with se, z — pooled per-deck, unweighted;
  (2) THE COMPANION CONTRAST: per common deck d, c(d) = m_all(d) − m_early(d);
      report mean/se/z over n_common (target 1,200). This is within-band,
      deck-matched — the robust class. Interpretation aid pre-stated: c ≈ the
      mid+late fires' contribution; c and the A1 primary (+0.49 ± 0.37) sum to
      M_all mechanically on common decks.
  (3) health only: n_records, n_paired per cell, n_failed from summaries.
No elo is quoted (house: the margin is the statistic).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import screen_lib as L  # noqa: E402

BASE = Path("/mnt/c/carc-shared/phasegate_a1")
ALL_CELLS = ["ARB_FULL", "ARB_FULL_EXT_L", "ARB_FULL_EXT_R"]
EARLY_CELLS = ["ARB_EARLY_L", "ARB_EARLY_R"]


def load_records(cell: str):
    out = []
    for p in sorted((BASE / cell).glob("seed*_a*.json")):
        out.append(json.loads(p.read_text()))
    return out


def pooled_margins(cells):
    recs = []
    for c in cells:
        recs.extend(load_records(c))
    return L.per_deck_margins(recs), len(recs)


def mean_se_z(vals):
    n = len(vals)
    m = sum(vals) / n
    var = sum((v - m) ** 2 for v in vals) / (n - 1)
    se = (var / n) ** 0.5
    return m, se, (m / se if se else float("nan")), n


def main():
    all_m, n_all = pooled_margins(ALL_CELLS)
    early_m, n_early = pooled_margins(EARLY_CELLS)
    common = sorted(set(all_m) & set(early_m))
    M_all = mean_se_z(list(all_m.values()))
    contrast = mean_se_z([all_m[d] - early_m[d] for d in common])
    out = {
        "reader": "read_a2_companion (frozen blind pre-EXT-data)",
        "label": "COMPANION READING — fires no branch (DESIGN §3.2/§4.4)",
        "n_records": {"all_pool": n_all, "early_pool": n_early},
        "widened_anchor_M_all": dict(zip(("M", "se", "z", "n_decks"), M_all)),
        "full_minus_early_contrast": dict(
            zip(("M", "se", "z", "n_common"), contrast)),
    }
    print(json.dumps(out, indent=2))
    (BASE / "A2_COMPANION.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
